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

locations = {
    "Toronto": "23603",
    "Mississauga": "15074",
    "North York": "16385",
    "Scarborough": "21323",
    "Markham": "14134",
    "Brampton": "2480",
    "Etobicoke": "6859",
    "Richmond Hill": "18986",
    "Oakville": "16611",
    "Thornhill": "23437",
    "Woodbridge": "25665",
    "Vaughan": "24363",
    "Pickering": "17530",
    "York": "25833",
    "Ajax": "141",
    "Concord": "4675",
    "East York": "6385",
    "Unionville": "23975",
    "Maple": "13999",
    "Bolton": "2242",
    "Stouffville": "22771",
    "King City": "11062",
    "Kleinburg": "11239",
    "Streetsville": "22819",
    "Ottawa": "16881",
    "Gormley": "8402",
    "Locust Hill": "13256",
    "Whitchurch Stouffville": "25289",
    "Cooksville": "4738",
    "Downsview": "5930",
    "Aurora": "779",
    "Hornby": "9873",
    "Montreal, QC": "15240",
    "Nobel": "16131",
    "Nobleton": "16135",
    "Oakwood": "16612",
    "Pickering Beach": "17531",
    "Port Credit": "18094",
    "Vancouver, BC": "24315",
    "Caledon East": "3150",
    "Calgary, AB": "3159",
    "Clarkson": "4338",
    "Edmonton, AB": "6493",
    "Golden, BC": "8319",
    "Haliburton": "8995",
    "Coffee Shops": "2512",
    "Restaurants": "827",
    "Unknown": "20014",
    "Bakeries": "2536",
    "Bars": "2468",
    "Catering": "2520",
    "Coffee Roasting": "1677",
    "Delicatessens": "2544",
    "Internet Cafes": "696",
    "Café": "12632",
    "Grocery Stores": "2510",
    "Coffee": "2603",
    "Italian Restaurants": "2630",
    "Ice Cream": "2704",
    "Beverage Supplies": "1753",
    "Bistro": "2574",
    "Pizza": "6324",
    "Franchising": "1121",
    "Tea": "3302",
    "Donuts": "2572",
    "Sandwiches": "2678",
    "Bagels": "2712",
    "Pastries": "2581",
}

DROPDOWN_OPTIONS = list(locations.keys())


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

    selector = Selector(text=company_info, type="json")

    first = lambda query: selector.jmespath(query).get("").strip()  # noqa: E731
    many = lambda query: ", ".join(  # noqa: E731
        set([value.strip() for value in selector.jmespath(query).getall()])
    )
    info = {
        "name": first("data.name"),
        "categories": many("data.categories[*].name"),
        "phone": many("data.phone[*].value"),
        "email": first("data.email.address"),
        "location": first("data.address.addressLine1"),
        "zip_code": first("data.address.postalcode"),
        "city": first("data.address.city.name"),
        "state": first("data.address.city.province.name"),
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

    sel = Selector(text=response, type="json")
    parsed = []

    for result in sel.jmespath("searchResult[0].merchants"):
        try:
            merchantId = result.jmespath("merchantId").get("").strip()
            if not merchantId:
                continue
            parsed.append(
                {
                    "name": merchantId,
                    "url": f"https://services.411.ca/business/{merchantId}?lang=EN",
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

    def make_json_data(page):
        """Create the json_data."""
        return {
            "search": [
                {
                    "collection": "MERCHANT",
                    "language": "EN",
                    "query": query,
                    "randomSeed": 4178732771847,
                    "userLocation": {
                        "approximateLocation": "43.755091,-79.347743",
                    },
                    "results": [
                        {
                            "type": "ROOT",
                            "from": 25 * (page - 1),
                            "count": 25,
                            "sort": "411_advertiser",
                        },
                    ],
                    "dimension": f"(city = {locations.get(location, 23603)})",
                },
            ],
        }

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

    BASE_URL = "https://services.411.ca/search-business/"

    companies = []
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
    }
    # Get the first page of the search results
    first_page_content = await make_request(
        session,
        BASE_URL,
        proxy=proxy,
        progress=progress,
        semaphore=semaphore,
        json=make_json_data(1),
        is_post=True,
        headers=headers,
    )
    previews = parse_search(first_page_content)

    if not previews or not progress.is_set():
        return companies

    # Scrape the first page of the search results
    companies.extend(await gather_companies(previews))
    if not progress.is_set():
        return companies

    sel = Selector(text=first_page_content, type="json")
    total_results = sel.jmespath("searchResult[0].summary.pagination.numFound").get(0)

    total_pages = int(math.ceil(int(total_results) / 25)) if total_results else 1
    try:
        for page in await asyncio.gather(
            *[
                make_request(
                    session,
                    BASE_URL,
                    semaphore=semaphore,
                    proxy=proxy,
                    progress=progress,
                    json=make_json_data(page),
                    is_post=True,
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
