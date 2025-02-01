import asyncio
import math
import threading
from typing import List, Optional

import aiohttp
from loguru import logger as log
from parsel import Selector
from typing_extensions import TypedDict
from yellowpages.proxy import Proxy
from yellowpages.utils import EventManager, make_request

event = EventManager()


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


def parse_companies(company_info) -> Company:
    """
    Parse the company information from the HTML response.

    Args:
        company_info (str): The HTML response containing the company information.

    Returns:
        Company: The parsed company information.
    """

    selector = Selector(text=company_info)

    companies = []
    for result in selector.css("ol.result-items > li.result-item"):
        try:
            first = lambda css: result.css(css).get("").strip()  # noqa: E731
            many = lambda css: ", ".join(  # noqa: E731
                set([value.strip() for value in result.css(css).getall()])
            )

            address = [
                first("span[data-yext='street']::text"),
                first("span[data-yext='postal-code']::text"),
                first("span[data-yext='city']::text"),
            ]

            info = {
                "name": first("h2[itemprop='name']::text"),
                "categories": many(
                    "div > div:nth-child(1) > div.flex.gap-4.mb-2\\.5.items-start > span > span::text"
                ),
                "phone": first("div[data-js-event='call']::attr(data-js-value)"),
                "email": first("div[data-js-event='email']::attr(data-js-value)"),
                "location": address[0],
                "zip_code": address[1],
                "city": address[2],
                "state": ", ".join(address),
            }
            companies.append(info)
            event.emit("update_total", 1)
        except Exception as e:
            log.error(f"Error parsing search results: {e}")
            continue
    return companies


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

    page = await make_request(
        session, url, semaphore=semaphore, proxy=proxy, progress=progress
    )

    if not (progress.is_set() or page):
        return

    try:
        companies_info = parse_companies(page)
        return companies_info
    except Exception as e:
        log.error(f"Error scraping company: {e}")


async def search(
    query: str,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    location: Optional[str] = None,
    proxy: Proxy = None,
    progress: threading.Event = threading.Event(),
) -> List[Company]:
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
        base_url = "https://www.goudengids.nl/nl/zoeken/"
        parameters = [query, location, str(page)]
        return base_url + "/".join(parameters)

    companies = []

    # Get the first page of the search results
    first_page_content = await make_request(
        session, make_search_url(1), proxy=proxy, progress=progress, semaphore=semaphore
    )

    companies.extend(parse_companies(first_page_content))

    if not progress.is_set():
        return companies

    # Get the total number of pages
    sel = Selector(text=first_page_content)
    total_results = sel.css("span.count::text").get("").strip().replace(" ", "")
    total_pages = int(math.ceil(int(total_results) / 20)) if total_results else 1
    try:
        for infos in await asyncio.gather(
            *[
                scrape_company(
                    make_search_url(page), session, proxy, progress, semaphore
                )
                for page in range(2, total_pages + 1)
                if progress.is_set()
            ]
        ):
            if not infos:
                continue
            companies.extend(infos)
    except Exception as err:
        log.error(f"Error scraping search results: {err}")

    return companies
