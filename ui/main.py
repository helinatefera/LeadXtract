import math
import random
import re
import time
import csv
import requests
from bs4 import BeautifulSoup

import customtkinter as ctk
from tkinter import filedialog, messagebox
from threading import Thread
import time

class YellowPageScraper:
    def __init__(self, business: str, location: str):
        self.business = business
        self.location = location

    def get_response(self, url: str):

        tries = 0
        try:
            response = requests.get(url)
            
            while tries < 4 and response.status_code != 200:
                tries += 1

                if tries == 3:
                    print("Error Persists")
                    print(response.text)
                    return False

                print(f"Error loading the page {url}. Trying again for {tries} time.")
                random_time = random.randint(5, 30)
                print(f"Waitin for {random_time}")
                time.sleep(random_time)

                response = requests.get(url)
        except Exception as err:
            print(err)
            tries += 1
            if tries > 3:
                return False
        return response.content

    def get_text(self, content):
        if content:
            return content.get_text()
        return ""

    def get_info(self, target_website: str) -> list:
        page_content = self.get_response(target_website)
        if page_content == False:
            return []

        page = BeautifulSoup(page_content, "html.parser")

        business_name = self.get_text(page.find("h1", {"class": "dockable business-name"}))
        if not business_name:
            return []

        categories = self.get_text(page.find("div", {"class": "categories"}))

        email = page.find("a", {"class": "email-business"})
        email = email.get("href").replace("mailto:", "") if email else ""

        phone_number = self.get_text(page.find("a", {"class": "phone dockable"}))

        pattern = r"<span>([^<]+)</span>([^,]+), ([A-Z]{2}) (\d{5})"
        address = page.find("span", {"class": "address"})
        location, city, state, zip_code = "", "", "", ""
        if address is not None:
            address = address.renderContents().decode("utf-8")
            match = re.search(pattern, address)
            if match:
                location, city, state, zip_code = match.groups()

        return [business_name, categories, email, phone_number, location, city, state, zip_code]

    def get_page_numer(self, content):
        pattern = r"of (\d+)"
        match = re.search(pattern, content)
        if match:
            total_pages = math.ceil(int(match.group(1)) / 30)
        else:
            total_pages = 1

        return total_pages

    def scrape(self):

        url = "https://www.yellowpages.com/search?search_terms=" f"{self.business}&geo_location_terms={self.location}"

        current_page = 1
        data = []
        while True:
            print("Loading page", current_page)
            page_content = self.get_response(url)
            if page_content == False or b"No results found" in page_content:
                break
            print("Page", current_page, "loaded")

            page = BeautifulSoup(page_content, "html.parser")
            search_results = page.find_all("div", class_="result") or []
            print(len(search_results), "resul found in page", current_page)

            for idx, result in enumerate(search_results):
                business_name = result.find("a", {"class": "business-name"})
                detail_page_url = "https://www.yellowpages.com{}".format(
                    business_name.get("href") if business_name else ""
                )
                info = self.get_info(detail_page_url)
                print("Info of page", current_page, "result", idx + 1, "extrcted")
                if info:
                    data.append(info)
            current_page += 1
            next_link = page.find("a", {"class": "next"})
            if next_link:
                url = "https://www.yellowpages.com{}".format(next_link.get("href"))
            else:
                break
        return data



ctk.set_appearance_mode("System")  # Set appearance mode to system theme
ctk.set_default_color_theme("blue")  # Set the color theme to blue

class BusinessScraperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Business Scraper")
        self.geometry("500x340")  # Set a fixed window size
        self.resizable(False, False)  # Disable window resizing

        # Add a title label at the top
        self.app_title = ctk.CTkLabel(self, text="Business Scraper Tool", pady=20, font=("Arial", 26, "bold"))
        self.app_title.pack()

        # Create a container for the form elements
        self.container = ctk.CTkFrame(self, corner_radius=8)
        self.container.pack(padx=20, pady=20, fill="both", expand=True)

        # Business Name Entry
        self.business_name_entry = ctk.CTkEntry(self.container, placeholder_text="Business Name", width=450, height=30, font=("Arial", 16), corner_radius=4
        )
        self.business_name_entry.pack(pady=20)

        # Location Entry
        self.location_entry = ctk.CTkEntry(self.container, placeholder_text="Location",  width=450, height=30, font=("Arial", 16), corner_radius=4)
        self.location_entry.pack(pady=0)

        # File Location Entry and Button
        self.file_location_frame = ctk.CTkFrame(self.container)
        self.file_location_frame.pack(fill="x", pady=15)

        self.file_location_entry = ctk.CTkEntry(self.file_location_frame, placeholder_text="Filename with location", width=290, height=30, font=("Arial", 16), corner_radius=4)
        self.file_location_entry.pack(side="left", padx=(5,5))
        
        self.select_file_button = ctk.CTkButton(self.file_location_frame, text="Select File", command=self.select_file, corner_radius=4)
        self.select_file_button.pack(side="right", padx=(0, 5))

        # Search Button
        self.search_button = ctk.CTkButton(self.container, text="Search", command=self.on_search, height=40, font=("Arial", 16), corner_radius=4)
        self.search_button.pack(pady=20)

        # Loading Label (hidden by default)
        self.loading_label = ctk.CTkLabel(self.container, text="Loading...", fg_color="red")

    def select_file(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".csv")
        if file_path:
            self.file_location_entry.delete(0, ctk.END)
            self.file_location_entry.insert(0, file_path)

    def on_search(self):
        business_name = self.business_name_entry.get()
        location = self.location_entry.get()
        file_location = self.file_location_entry.get()

        if not business_name or not location or not file_location:
            messagebox.showwarning("Warning", "Please enter all required fields.")
            return

        # Show the loading label and disable the search button
        self.loading_label.pack(pady=10)
        self.search_button.configure(state="disabled")
        self.update()

        # Start the scraping process in a background thread
        scrape_thread = Thread(target=self.run_scraping, args=(business_name, location, file_location))
        scrape_thread.start()

    def run_scraping(self, business_name, location, file_location):
        # Simulate a scraping process
        
        yellowpage = YellowPageScraper(business_name, location)
        data = yellowpage.scrape()
        if not data:
            messagebox.showerror("Error Scraping Data", "Query not found")

        cols = ["business_name", "categories", "email", "phone_number", "location", "city", "state", "zip_code"]
        with open(file_location, "w") as f:
            cw = csv.writer(f)
            cw.writerows([cols]+ data)
        # Once scraping is complete, hide the loading label, show success message, and re-enable the search button
        self.loading_label.pack_forget()
        self.search_button.configure(state="normal")
        messagebox.showinfo("Success", "Scraping completed and data is saved.")

if __name__ == "__main__":
    app = BusinessScraperApp()
    app.mainloop()
