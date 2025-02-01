import asyncio
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
    """type hint container for company data found"""

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
    selector = Selector(text=company_info, type="json")

    companies = []

    for result in selector.jmespath("list.out.base.results"):
        try:
            first = lambda query: result.jmespath(query).get("").strip()  # noqa: E731
            many = lambda query: ", ".join(  # noqa: E731
                set([value.strip() for value in result.jmespath(query).getall()])
            )
            info = {
                "name": first("ds_ragsoc"),
                "categories": first("ds_cat"),
                "phone": many("ds_ls_telefoni"),
                "email": many("ds_ls_email"),
                "location": first("addr"),
                "zip_code": first("ds_cap"),
                "city": first("loc"),
                "state": first("reg"),
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
        base_url = "https://www.paginegialle.it/ricerca/%(what)s/%(where)s/p-%(page_num)s?output=json"
        parameters = {
            "what": query,
            "where": location,
            "page_num": page,
        }
        return base_url % parameters

    companies = []

    # Get the first page of the search results
    first_page_content = await make_request(
        session, make_search_url(1), proxy=proxy, progress=progress, semaphore=semaphore
    )
    # from pprint import pprint

    companies.extend(parse_companies(first_page_content))

    if not progress.is_set():
        return companies

    # Get the total number of pages
    sel = Selector(text=first_page_content)
    total_pages = int(sel.jmespath("list.pagination.numPages").get(0))

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
