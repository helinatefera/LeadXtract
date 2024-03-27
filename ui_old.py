import asyncio
import csv
import pathlib
import threading
import time
from tkinter import filedialog, messagebox

import aiohttp
import customtkinter as ctk
from loguru import logger as log
from PIL import Image

from yellowpages.proxy import Proxy
from yellowpages.scraper import search
from yellowpages.utils import LoadingAnimation

ctk.set_appearance_mode("System")  # Set appearance mode to system theme
ctk.set_default_color_theme("blue")  # Set the color theme to blue


class BusinessScraperApp(ctk.CTk):
    """
    Business Scraper Application
    """

    def __init__(self):

        super().__init__()

        self.progress = threading.Event()
        self.loading_animation = LoadingAnimation(progress=self.progress)
        images_folder = pathlib.Path(pathlib.Path(__file__).parent / "images/")

        self.title("Yellow Pages Scraper v1.0")
        self.geometry("500x610")  # Set a fixed window size
        self.resizable(False, False)  # Disable window resizing

        self.header_container = ctk.CTkFrame(self, height=10, corner_radius=4)
        self.header_container.pack(padx=20, pady=(10, 5), fill="both", expand=False)

        # Add a title label at the top
        self.app_title = ctk.CTkLabel(
            self.header_container,
            text="Business Information Scraper Tool",
            font=("Segoe UI", 20, "bold"),
        )
        self.app_title.pack(pady=15)

        # Create a container for the form elements
        self.container = ctk.CTkFrame(self, corner_radius=8)
        self.container.pack(padx=20, pady=30, fill="both", expand=True)

        # Business Name Entry
        self.business_name_entry = ctk.CTkEntry(
            self.container,
            placeholder_text="Business Names",
            width=450,
            height=30,
            font=("Segoe UI Variable Text", 16),
            corner_radius=4,
        )
        self.business_name_entry.pack(pady=(20, 2), padx=10)
        # Business Name help text
        self.business_name_help = ctk.CTkLabel(
            self.container,
            text="* Enter the business names separated by comma.",
            font=("Segoe UI Variable Small", 12, "italic"),
        )
        self.business_name_help.pack(pady=(0, 10), padx=10, anchor="w")

        # Location Entry
        self.location_entry = ctk.CTkEntry(
            self.container,
            placeholder_text="Locations",
            width=450,
            height=30,
            font=("Segoe UI Variable Text", 16),
            corner_radius=4,
        )
        self.location_entry.pack(pady=(10, 2), padx=10)
        # Location help text
        self.location_help = ctk.CTkLabel(
            self.container,
            text="* Enter the location names separated by comma.",
            font=("Segoe UI Variable Small", 12, "italic"),
        )
        self.location_help.pack(pady=(0, 10), padx=10, anchor="w")

        self.proxy_file_location_frame = ctk.CTkFrame(self.container)
        self.proxy_file_location_frame.pack(padx=10, pady=10, fill="x")

        self.proxy_file_location_entry = ctk.CTkEntry(
            self.proxy_file_location_frame,
            placeholder_text="Proxy file location",
            width=290,
            height=30,
            font=("Segoe UI Variable Text", 16),
            corner_radius=4,
        )
        self.proxy_file_location_entry.pack(side="left", pady=(0, 0), padx=0)

        self.select_proxy_file_button = ctk.CTkButton(
            self.proxy_file_location_frame,
            text="Select Proxy File",
            command=self.select_proxy_file,
            font=("Segoe UI Variable Text", 14),
            corner_radius=4,
        )
        self.select_proxy_file_button.pack(side="right", pady=(0, 0), padx=0)
        # Proxy File help text
        self.proxy_file_help = ctk.CTkLabel(
            self.container,
            text="* file should contain proxies in the format ip:port:username:password",
            font=("Segoe UI Variable Small", 12, "italic"),
        )
        self.proxy_file_help.pack(pady=(0, 10), padx=10, anchor="w")
        # File Location Entry and Button
        self.file_location_frame = ctk.CTkFrame(self.container)
        self.file_location_frame.pack(padx=10, pady=10, fill="x")

        self.file_location_entry = ctk.CTkEntry(
            self.file_location_frame,
            placeholder_text="File location",
            width=290,
            height=30,
            font=("Segoe UI Variable Text", 16),
            corner_radius=4,
        )
        self.file_location_entry.pack(side="left", pady=(0, 0), padx=0)

        self.select_file_button = ctk.CTkButton(
            self.file_location_frame,
            text="Select File",
            command=self.select_file_location,
            font=("Segoe UI Variable Text", 14),
            corner_radius=4,
        )
        self.select_file_button.pack(side="right", pady=(0, 0), padx=0)

        # File Location help text
        self.file_location_help = ctk.CTkLabel(
            self.container,
            text="* Select the location where the file will be saved.",
            font=("Segoe UI Variable Small", 12, "italic"),
        )
        self.file_location_help.pack(pady=(0, 10), padx=10, anchor="w")

        # Progress Bar hidden by default
        self.progress_bar = ctk.CTkProgressBar(self.container, width=450, height=10)
        self.progress_bar.pack(pady=10, padx=10)

        search_icon = ctk.CTkImage(
            Image.open(images_folder / "search.png"), size=(20, 20)
        )
        # Search Button
        self.search_button = ctk.CTkButton(
            self.container,
            text="Search",
            command=self.on_search,
            height=40,
            font=("Nyala", 20),
            corner_radius=4,
            image=search_icon,
            compound="right",
        )
        self.search_button.pack(side="left", pady=20, padx=30)

        self.cancel = ctk.CTkButton(
            self.container,
            text="Cancel",
            text_color="white",
            command=self.on_cancel,
            height=40,
            font=("Arial", 20, "bold"),
            corner_radius=4,
            state="disabled",
            fg_color="#aaa",
        )
        self.cancel.pack(side="right", pady=20, padx=30)

    def select_proxy_file(self):
        file_path = filedialog.askopenfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt")],
            title="Select Proxy File",
        )
        if file_path:
            self.proxy_file_location_entry.delete(0, ctk.END)
            self.proxy_file_location_entry.insert(0, file_path)

    def select_file_location(self):
        file_path = filedialog.asksaveasfilename(filetypes=[("CSV Files", "*.csv")])
        if file_path:
            self.file_location_entry.delete(0, ctk.END)
            self.file_location_entry.insert(0, file_path)

    def on_cancel(self):
        self.progress.clear()
        self.search_button.configure(state="normal")
        self.cancel.configure(state="disabled", fg_color="#aaa")
        self.progress_bar.stop()
        self.update()

    def on_search(self):
        business_names = self.business_name_entry.get()

        if len(business_names) == 0:
            messagebox.showerror("Error", "Please enter business names.")
            return

        locations = self.location_entry.get()

        if len(locations) == 0:
            messagebox.showerror("Error", "Please enter locations.")
            return

        business_names = business_names.split(",")
        locations = locations.split(",")

        if len(business_names) != len(locations):
            messagebox.showerror(
                "Error",
                "The number of business names should match the number of locations.",
            )
            return

        file_location = self.file_location_entry.get()
        if not file_location:
            messagebox.showerror("Error", "Please select a file location.")
            return

        proxy_file_location = self.proxy_file_location_entry.get()

        self.progress.set()
        self.search_button.configure(state="disabled")
        self.cancel.configure(state="normal", fg_color="red")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        self.update()

        queries = list(zip(business_names, locations))

        scrape_thread = threading.Thread(
            target=self.run_scraping,
            args=(queries, file_location, proxy_file_location),
        )
        scrape_thread.start()

    async def run(self, query, progress, semaphore, proxy=None):
        BASE_HEADERS = {
            "accept-language": "en-US,en;q=0.9",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "accept-language": "en-US;en;q=0.9",
            "accept-encoding": "gzip, deflate, br",
        }

        result_searchs = []
        async with aiohttp.ClientSession(
            headers=BASE_HEADERS,
            connector=aiohttp.TCPConnector(ssl=False),
        ) as session:
            try:
                search_result = await asyncio.gather(
                    *[
                        search(
                            business_name,
                            location=location,
                            session=session,
                            proxy=proxy,
                            progress=progress,
                            semaphore=semaphore,
                        )
                        for business_name, location in query
                        if progress.is_set()
                    ],
                )

                for result in search_result:
                    if isinstance(result, list):
                        result_searchs.extend(result)
            except Exception as e:
                log.error(e)

        return result_searchs

    def run_scraping(self, queries, file_location, proxy_file_location):
        self.loading_animation.start()

        proxy = Proxy(proxy_file_location)
        start_time = time.perf_counter()
        semaphore = asyncio.Semaphore(10)  # Limit the number of concurrent requests
        result = asyncio.run(self.run(queries, self.progress, semaphore, proxy=proxy))

        scraped_data = [row for row in result if isinstance(row, dict)]

        if scraped_data:
            self.save_to_csv(scraped_data, file_location)
            if self.progress.is_set():
                self.cancel.invoke()
            messagebox.showinfo(
                "Data Scraped!",
                f"Total of {len(scraped_data)} data is saved to {file_location}",
            )
        else:
            messagebox.showerror("Error", "No data was scraped.")

        end_time = time.perf_counter()
        total_time = end_time - start_time
        print(
            f"\n---Finished in: {total_time:02f} seconds---\n"
            f"Total of {len(scraped_data)} business companies information gathered."
        )

    def save_to_csv(self, data, file_location):
        with open(file_location, "w") as f:
            cw = csv.DictWriter(f, fieldnames=data[0].keys(), lineterminator="\n")
            cw.writeheader()
            cw.writerows(data)
