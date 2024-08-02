import asyncio
import math
import re
import threading
from typing import List, Optional
from urllib.parse import urlencode

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
        company_info (str): The JSON response containing company information.

    Returns:
        Company: The parsed company information.
    """
    selector = Selector(text=company_info, type="json")

    companies = []

    for result in selector.jmespath("pageProps.results.nodes"):
        try:
            first = lambda query: result.jmespath(query).get("").strip()
            many = lambda query: ", ".join(
                set([value.strip() for value in result.jmespath(query).getall()])
            )
            info = {
                "name": first("name"),
                "categories": first("industry"),
                "phone": many("tel"),
                "location": first("address"),
                "zip_code": first("zip"),
                "city": first("city"),
                "state": first("state"),
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


async def get_suggested_location(session: aiohttp.ClientSession, location: str) -> str:
    url = "https://www.herold.at/api/geo/search/?term=" + location
    async with session.get(url) as response:
        if response.ok:
            data = await response.json()
            if data:
                return data[0]["label"]
    return location


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

    # Locate close matches to the location
    location = await get_suggested_location(session, location)

    # The website API uses a token to make requests which changes
    # every time the website is built (Next.js) so we need to get
    # the build ID from the home page
    home_page = await make_request(session, "https://www.herold.at/", progress=progress)
    pattern = re.compile(r'"buildId":\s*"([a-zA-Z0-9-]+)"')
    if not home_page or re.search(pattern, home_page) is None:
        return []
    token = re.search(pattern, home_page).group(1)

    def make_search_url(page):
        """Create the search URL."""
        # token = awaget_session_token()
        base_url = f"https://www.herold.at/_next/data/{token}/gelbe-seiten/suche.json?"
        parameters = {
            "userTerm": query,
            "geoLabel": location,
            "seite": page,
        }
        return base_url + urlencode(parameters)

    companies = []
    # print("Search URL", make_search_url(1), file=open("search_url.txt", "w"))
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
    total_count = int(sel.jmespath("pageProps.results.totalCount").get(0))
    total_pages = math.ceil(total_count // 30)
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
