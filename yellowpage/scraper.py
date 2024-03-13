import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager


class YellowPageScraper:
    def __init__(self, business: str, location: str, average_waiting_time: int = 10):
        self.business = business
        self.location = location
        self.average_waiting_time = average_waiting_time

        options = self._get_options()

        self.driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=options)

    def _get_options(self):
        options = webdriver.FirefoxOptions()
        options.add_argument("log-level=3")
        options.add_argument("--disable-gpu")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--ignore-certificate-errors-spki-list")
        options.add_argument("--ignore-ssl-errors")
        options.add_argument("--headless")

        return options

    def __del__(self):
        self.driver.quit()

    def scrape(self):

        # Go to search results
        url = "https://www.yellowpages.com/search?search_terms=" f"{self.business}&geo_location_terms={self.location}"

        self.driver.get(url)

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        
        results = soup.find_all("div", class_="result")
        data = []
        for result in results:
            business_name = result.find("a", class_="business-name").get_text()
            categories = ", ".join([child.get_text() for child in result.find("div", class_="categories").contents])

            phone_number = result.find("div", class_="phones phone primary")
            phone_number = phone_number.get_text() if phone_number else ""

            street_address = result.find("div", class_="street-address")
            street_address = street_address.get_text() if street_address else ""

            locality = result.find("div", class_="locality")
            locality = locality.get_text() if locality else ""

            data.append([business_name, categories, phone_number, street_address, locality])

        return data

        time.sleep(self.average_waiting_time)


# yellowpage = YellowPageScraper("cafe", "hawassa")

# data = yellowpage.scrape()
