import asyncio
import math
import re
import threading
from typing import List, Optional
from urllib.parse import urlencode, urljoin

import aiohttp
from loguru import logger as log
from parsel import Selector
from typing_extensions import TypedDict
from yellowpages.proxy import Proxy
from yellowpages.utils import EventManager, make_request

event = EventManager()


class Preview(TypedDict):
    """Type hint container for preview data. This object just helps us to keep track what results we'll be getting"""

    name: str
    url: str


class Company(TypedDict):
    """type hint container for company data found on yellowpages.com"""

    name: str
    categories: List[str]
    phone: str
    email: str
    location: str
    city: str
    state: str
    zip_code: str


def parse_company(company_info) -> Company:
    """
    Parse the company information from the HTML response.

    Args:
        company_info (str): The HTML response containing the company information.

    Returns:
        Company: The parsed company information.
    """

    selector = Selector(text=company_info)

    first = lambda css: selector.css(css).get("").strip()  # noqa: E731
    many = lambda css: ", ".join(  # noqa: E731
        set([value.strip() for value in selector.css(css).getall()])
    )
    together = lambda css, sep=" ": sep.join(selector.css(css).getall())  # noqa: E731

    def _parse_address(address: str):
        pattern = r"<span>([^<]+)</span>([^,]+), ([A-Z]{2}) (\d{5})"
        location, city, state, zip_code = [""] * 4
        match = re.search(pattern, address)
        if match:
            location, city, state, zip_code = match.groups()
        return [location, city, state, zip_code]

    address = _parse_address(together(".address"))
    result = {
        "name": first("h1.business-name::text"),
        "categories": many(".categories>a::text"),
        "phone": first(".phone::attr(href)").replace("tel:", ""),
        "email": first(".email-business::attr(href)").replace("mailto:", ""),
        "location": address[0],
        "city": address[1],
        "state": address[2],
        "zip_code": address[3],
    }
    return result


def parse_search(response) -> Preview:
    """
    Parse yellowpages.com search page for business preview data.

    Args:
        response (str): The HTML response containing the search results.

    Returns:
        Preview: The parsed preview data.
    """

    sel = Selector(text=response)
    parsed = []

    for result in sel.css(".organic div.result"):
        try:
            first = lambda css: result.css(css).get("").strip()  # noqa: E731
            name = first("a.business-name ::text")
            if not name:
                continue
            parsed.append(
                {
                    "name": name,
                    "url": urljoin(
                        "https://www.yellowpages.com/",
                        first("a.business-name ::attr(href)"),
                    ),
                }
            )
        except Exception as e:
            log.error(f"Error parsing search results: {e}")
            continue
    return parsed


async def scrape_company(
    url: str,
    session: aiohttp.ClientSession,
    proxy: Proxy,
    progress: threading.Event,
    semaphore: asyncio.Semaphore,
) -> Company:
    """
    Scrape yellowpage.com company page details.

    Args:
        url (str): The URL of the company page.
        session (aiohttp.ClientSession): The aiohttp session object.
        proxy (Proxy): The proxy object.

    Returns:
        Company: The company information.
    """
    header = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit"
        "/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
    }

    page = await make_request(
        session,
        url,
        semaphore=semaphore,
        proxy=proxy,
        progress=progress,
        headers=header,
    )

    if not (progress.is_set() or page):
        return

    try:
        company_info = parse_company(page)
        if company_info["name"] != "":
            event.emit("update_total", 1)
            return company_info
    except Exception as e:
        log.error(f"Error scraping company: {e}")


async def search(
    query: str,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    location: Optional[str] = None,
    proxy: Proxy = None,
    progress: threading.Event = threading.Event(),
) -> List[Preview]:
    """
    Search yellowpages.com for business preview information scraping all of the pages.

    Args:
        query (str): The search query.
        session (aiohttp.ClientSession): The aiohttp session object.
        location (str): The location to search in.
        proxy (str): The proxy to use.

    Returns:
        List[Preview]: The list of preview data.
    """

    def make_search_url(page):
        """Create the search URL."""
        base_url = "https://www.yellowpages.com/search?"
        parameters = {
            "search_terms": query,
            "geo_location_terms": location,
            "page": page,
        }
        return base_url + urlencode(parameters)

    async def gather_companies(previews: List[Preview]) -> List[Company]:
        """Gather the previews."""
        _companies = []

        for result in await asyncio.gather(
            *[
                scrape_company(
                    result["url"],
                    session=session,
                    proxy=proxy,
                    progress=progress,
                    semaphore=semaphore,
                )
                for result in previews
                if progress.is_set()
            ]
        ):
            if result and isinstance(result, (dict, Company)):
                _companies.append(result)

        return _companies

    companies = []

    header = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit"
        "/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
    }
    # Get the first page of the search results
    first_page_content = await make_request(
        session,
        make_search_url(1),
        proxy=proxy,
        progress=progress,
        semaphore=semaphore,
        headers=header,
    )

    previews = parse_search(first_page_content)

    if not previews or not progress.is_set():
        return companies

    # Scrape the first page of the search results
    companies.extend(await gather_companies(previews))

    if not progress.is_set():
        return companies

    # Get the total number of pages
    sel = Selector(text=first_page_content)
    total_results = sel.css(".pagination>span::text ").re(r"of (\d+)")
    total_pages = int(math.ceil(int(total_results[0]) / 30)) if total_results else 1

    # Scrape the rest of the pages
    try:
        for page in await asyncio.gather(
            *[
                make_request(
                    session,
                    make_search_url(page),
                    semaphore=semaphore,
                    proxy=proxy,
                    progress=progress,
                )
                for page in range(2, total_pages + 1)
                if progress.is_set()
            ]
        ):
            if not progress.is_set():
                break

            if not page:
                continue

            page_previews = parse_search(page)

            if not page_previews:
                continue

            companies.extend(await gather_companies(page_previews))
    except Exception as err:
        log.error(f"Error scraping search results: {err}")

    return companies
