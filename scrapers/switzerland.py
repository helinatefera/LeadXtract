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

    selector = Selector(text=company_info, type="json")

    companies = []

    for entry in selector.jmespath(
        "data.search.entries[?entry.entryType=='BUSINESS'].entry"
    ):
        try:
            first = lambda query: entry.jmespath(query).get("")
            many = lambda query: ", ".join(
                set([value for value in entry.jmespath(query).getall()])
            )
            info = {
                "name": first("title"),
                "categories": many("categories.all[*].name.en"),
                "phone": many("contacts[?__typename=='PhoneContact'].value"),
                "email": many("contacts[?__typename=='EmailContact'].value"),
                "location": first("address.streetLine"),
                "zip_code": first("address.zipCode"),
                "city": first("address.city"),
                "state": first("address.cantonCode"),
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
    **kwargs: dict,
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
        session,
        url,
        semaphore=semaphore,
        proxy=proxy,
        progress=progress,
        is_post=True,
        **kwargs,
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

    def make_json_data(page):
        """Create the json_data."""
        return {
            "operationName": "search",
            "variables": {
                "debugMode": True,
                "what": query,
                "where": location,
                "pagination": {
                    "start": (page - 1) * 25,
                    "limit": 25,
                },
                "q": "",
            },
            "query": "query search($what:String$where:String$q:String$pagination:PaginationInformation!$debugMode:Boolean=true){search(options:{what:$what,where:$where,q:$q,debugMode:$debugMode}pagination:$pagination){total totalBusinesses entries{entry{entryType title address{streetLine zipCode city cantonCode}contacts{value __typename}categories{all{name{en}}}}}}}",
        }

    BASE_URL = "https://www.local.ch/api/graphql"

    companies = []
    # Get the first page of the search results

    first_page_content = await make_request(
        session,
        BASE_URL,
        proxy=proxy,
        progress=progress,
        semaphore=semaphore,
        json=make_json_data(1),
        is_post=True,
    )

    companies.extend(parse_companies(first_page_content))

    if not progress.is_set():
        return companies

    # Get the total number of pages
    sel = Selector(text=first_page_content, type="json")
    total_results = sel.jmespath("data.search.total").get(0)
    total_pages = int(math.ceil(int(total_results) / 25)) if total_results else 1
    try:
        for infos in await asyncio.gather(
            *[
                scrape_company(
                    BASE_URL,
                    session,
                    proxy,
                    progress,
                    semaphore,
                    json=make_json_data(page),
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
