import asyncio
import math
import threading
from typing import List, Optional
from urllib.parse import urljoin

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
    """
    Type hint container for company data found in the search results.
    This object just helps us to keep track what results we'll be getting.
    """

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

    first = lambda css: selector.css(css).get("").strip()
    many = lambda css: ", ".join(
        set([value.strip() for value in selector.css(css).getall()])
    )

    info = {
        "name": first("h1[itemprop='name'] > span::text"),
        "categories": many("a.category >::text"),
        "phone": many("a[href*=tel]::attr(href)").replace("tel:", ""),
        "email": (
            first("a[href*=mailto]::attr(href)").split("?")[0].replace("mailto:", "")
        ),
        "location": first("span[data-yext='street']::text"),
        "zip_code": first("span[data-yext='postal-code']::text"),
        "city": first("span[data-yext='city-district']::text"),
        "state": first("span[data-yext='city']::text"),
    }
    return info


def parse_search(response) -> Preview:
    """
    Parse search page for business preview data.

    Args:
        response (str): The HTML response containing the search results.

    Returns:
        Preview: The parsed preview data.
    """

    sel = Selector(text=response)
    parsed = []

    for result in sel.css("[itemprop='itemListElement']"):
        try:
            first = lambda css: result.css(css).get("").strip()
            name = first("h2[itemprop='name'] > span::text")
            if not name:
                continue
            parsed.append(
                {
                    "name": name,
                    "url": urljoin(
                        "https://www.goldenpages.be/",
                        first("a[data-ta='MoreInfoClick']::attr(href)"),
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
    Scrape company page details.

    Args:
        url (str): The URL of the company page.
        session (aiohttp.ClientSession): The aiohttp session object.
        proxy (Proxy): The proxy object.

    Returns:
        Company: The company information.
    """

    page = await make_request(
        session, url, semaphore=semaphore, proxy=proxy, progress=progress
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
    Search for business preview information scraping all of the pages.

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
        base_url = "https://www.goldenpages.be/search/"
        parameters = [query, location, str(page)]
        return base_url + "/".join(parameters)

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
                companies.append(result)

        return _companies

    companies = []
    # Get the first page of the search results
    first_page_content = await make_request(
        session, make_search_url(1), proxy=proxy, progress=progress, semaphore=semaphore
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
    total_results = sel.css("span.count::text").get("").strip().replace(" ", "")
    total_pages = int(math.ceil(int(total_results) / 20)) if total_results else 1

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
