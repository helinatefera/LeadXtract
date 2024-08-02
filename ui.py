import asyncio
import csv
import os
import pathlib
import sys
import threading
import time
from tkinter import filedialog, messagebox

import aiohttp
import customtkinter as ctk
from loguru import logger as log

from yellowpages.proxy import Proxy
from yellowpages.scrapers import Mapper
from yellowpages.utils import LoadingAnimation, resource_path

PROXY_FILE = ".proxies"


class Redirect:
    def __init__(self, widget):
        self.widget = widget

    def write(self, text):
        if text.startswith("\r"):
            self.widget.delete("end-1c linestart", "end-1c lineend")
        self.widget.insert(ctk.END, text)
        self.widget.see(ctk.END)

    def flush(self):
        pass


ctk.set_appearance_mode("light")  # Set appearance mode to system theme


class DropdownMultiSelect(ctk.CTkFrame):
    def __init__(self, master, items, **kwargs):
        super().__init__(master, **kwargs)

        # Toggle button to open/close the dropdown
        self.toggle_button = ctk.CTkButton(
            self, text="Select Location", command=self.toggle
        )
        self.toggle_button.pack(fill="x")

        # Scrollable frame to hold the checkboxes
        self.scrollable_frame = ctk.CTkScrollableFrame(self, height=50)
        self.content_frame = ctk.CTkFrame(
            self.scrollable_frame, height=50
        )  # Create a frame inside the scrollable frame
        self.content_frame.pack(pady=(0, 15), padx=0, fill="x")
        self.scrollable_frame.pack(pady=(0, 15), padx=0, fill="x")
        # self.location_dropdown.
        self.scrollable_frame.pack_forget()  # Start hidden

        self.vars = {}
        self.checkboxes = []

        # Populate with initial items
        self.set_items(items)

        self.currently_visible = False

    def toggle(self):
        if self.currently_visible:
            self.scrollable_frame.pack_forget()
        else:
            self.scrollable_frame.pack(pady=(0, 15), padx=0, fill="x")
        self.currently_visible = not self.currently_visible

    def get_selected_items(self):
        return [item for item, var in self.vars.items() if var.get() == 1]

    def set_items(self, items):
        # Clear the existing checkboxes
        for cb in self.checkboxes:
            cb.destroy()
        self.checkboxes.clear()
        self.vars.clear()

        # Add new checkboxes based on the new items list
        row = 0
        col = 0
        max_cols = 5  # Max columns in a row

        for index, item in enumerate(items):
            var = ctk.IntVar()
            cb = ctk.CTkCheckBox(self.content_frame, text=item, variable=var)
            cb.grid(row=row, column=col, sticky="w", padx=10, pady=2)
            if col == max_cols - 1:
                row += 1
                col = 0
            else:
                col += 1

            self.vars[item] = var
            self.checkboxes.append(cb)

    def get(self):
        return ",".join(self.get_selected_items())


class ProxyConfigPopup(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(fg_color="#ddd", *args, **kwargs)
        self.geometry("400x500")
        self.resizable(False, False)  # Disable window resizing

        self.title("Proxy Settings")

        self.proxy_list = ctk.CTkTextbox(
            self,
            font=("Segoe UI Variable Text", 12),
            corner_radius=0,
            border_color="#ddd",
        )
        self.proxy_list.pack(padx=20, pady=15, fill="both", expand=True)

        self.save_button = ctk.CTkButton(
            self,
            text="SAVE",
            command=self.save_proxy_list,
            font=("Segoe UI Variable Text", 16),
            corner_radius=0,
            fg_color="#009f3b",
            height=45,
            width=125,
        )
        self.save_button.pack(pady=(0, 10), padx=20, side="right")

        if pathlib.Path(PROXY_FILE).exists():
            with open(PROXY_FILE, "r+") as proxies:
                self.proxy_list.insert("end", proxies.read())

    def close(self):
        try:
            self.master.focus()
            self.destroy()
        except:
            pass

    def save_proxy_list(self):
        proxy = self.proxy_list.get("0.0", "end-1c")
        with open(PROXY_FILE, "w") as proxies:
            proxies.write(proxy)


class YellowPagesScraperUI(ctk.CTk):
    """
    Yellow Pages Scraper UI Application
    """

    def __init__(self):
        self.fg_color = "#f9c852"

        super().__init__(fg_color=self.fg_color)

        self.progress = threading.Event()
        self.loading_animation = LoadingAnimation(progress=self.progress)
        self.mapper = Mapper()
        # self.iconbitmap(resource_path("icon.ico"))

        self.title("Yellow Pages Scraper v1.0")
        self.geometry("900x610")  # Set a fixed window size
        self.resizable(False, False)  # Disable window resizing

        self.websites = self.mapper.get_options()

        if not self.websites:
            messagebox.showerror("Error", "No scraper modules found.")
            sys.exit(1)

        # Create a container for the proxy button
        self.proxy_container = ctk.CTkFrame(
            self, corner_radius=0, fg_color="transparent"
        )
        self.proxy_container.pack(padx=30, pady=20, fill="both")

        self.select_proxy_file_button = ctk.CTkButton(
            self.proxy_container,
            text="PROXY SETTINGS",
            command=self.select_proxy_file,
            font=("Segoe UI Variable Text", 14),
            corner_radius=0,
            fg_color="#4b4a4b",
            height=45,
            width=200,
        )
        self.select_proxy_file_button.pack(pady=0, padx=0, side="right")

        # Create a dropdown menu for selecting the scraping website

        self.scraping_website_dropdown = ctk.CTkComboBox(
            self.proxy_container,
            font=("Segoe UI Variable Text", 14),
            corner_radius=0,
            fg_color="#fff",
            height=45,
            width=225,
            values=self.websites,
            state="readonly",
            command=self.set_scraping_website,
        )
        self.scraping_website_dropdown.pack(pady=0, padx=0, side="left")

        self.scraping_website_dropdown.set(self.websites[0])
        self.website = self.websites[0]

        # Create a container for the form elements
        self.search_container = ctk.CTkFrame(
            self, corner_radius=8, fg_color="transparent"
        )
        self.search_container.pack(padx=30, pady=0, fill="both")

        # Business Name Entry
        self.keyowrds_entry = ctk.CTkEntry(
            self.search_container,
            placeholder_text="Keywords",
            font=("Segoe UI Variable Text", 16),
            corner_radius=3,
            height=45,
            border_color="#ddd",
        )
        # Add padding inside the entry
        self.keyowrds_entry.pack(pady=(0, 15), padx=0, fill="x")

        self.location_entry = ctk.CTkEntry(
            self.search_container,
            placeholder_text="Locations",
            font=("Segoe UI Variable Text", 16),
            corner_radius=3,
            height=45,
            border_color="#ddd",
        )
        # Add padding inside the entry

        self.location_dropdown = DropdownMultiSelect(
            self.search_container,
            items=[],
            # font=("Segoe UI Variable Text", 16),
            corner_radius=3,
            height=45,
            border_color="#ddd",
            # state="readonly",
        )
        self.location_widget = None
        self.set_dropdown()

        self.container = ctk.CTkFrame(self, corner_radius=8, fg_color="transparent")
        self.container.pack(padx=30, pady=0, fill="both")

        self.select_save_as_button = ctk.CTkButton(
            self.container,
            text="SAVE FILE AS",
            command=self.select_file_location,
            font=("Segoe UI Variable Text", 16),
            corner_radius=0,
            fg_color="#0769b2",
            height=45,
            width=200,
        )
        self.select_save_as_button.pack(pady=0, padx=0, side="left")

        self.stop_button = ctk.CTkButton(
            self.container,
            text="STOP",
            command=self.on_cancel,
            font=("Segoe UI Variable Text", 16),
            corner_radius=0,
            fg_color="#e00024",
            height=45,
            width=125,
        )
        self.stop_button.pack(pady=0, padx=10, side="right")

        self.start_button = ctk.CTkButton(
            self.container,
            text="START",
            command=self.on_search,
            font=("Segoe UI Variable Text", 16),
            corner_radius=0,
            fg_color="#009f3b",
            height=45,
            width=125,
        )
        self.start_button.pack(pady=0, padx=0, side="right")

        self.log_text = ctk.CTkTextbox(
            self,
            corner_radius=3,
            border_color="#ddd",
            fg_color="#000",
            text_color="#fff",
            font=("Segoe UI Variable Text", 14),
            spacing1=1,
        )

        self.log_text.pack(
            padx=30, pady=15, fill="both", expand=True, ipadx=300, ipady=30
        )
        self.log_text.bind("<Key>", lambda e: "break")
        sys.stdout = Redirect(self.log_text)
        sys.stderr = sys.stdout

        self.toplevel_window = None
        self.file_path = None

    def set_dropdown(self):
        dropdowns = self.mapper.get_dropdown(self.website)
        if not dropdowns:
            self.location_dropdown.pack_forget()
            self.location_entry.pack(pady=(0, 15), padx=0, fill="x")
            self.location_widget = self.location_entry
            return
        self.location_entry.pack_forget()
        self.location_dropdown.set_items(dropdowns)
        self.location_dropdown.pack(pady=(0, 15), padx=0, fill="x")
        self.location_widget = self.location_dropdown

    def set_scraping_website(self, selected):
        self.website = selected
        self.set_dropdown()

    def select_proxy_file(self):
        if not self.toplevel_window or not self.toplevel_window.winfo_exists():
            self.toplevel_window = ProxyConfigPopup(self)
            self.after(100, self.toplevel_window.focus)
        else:
            self.toplevel_window.focus()
        self.toplevel_window.deiconify()

    def select_file_location(self):
        self.file_path = filedialog.asksaveasfilename(
            title="Save the file on your computer", filetypes=[("CSV Files", "*.csv")]
        )

    def on_cancel(self):
        self.progress.clear()
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled", fg_color="#aaa")
        self.update()

    def on_search(self):
        keywords = self.keyowrds_entry.get()

        if len(keywords) == 0:
            messagebox.showerror("Error", "Please enter business names.")
            return

        locations = self.location_widget.get()

        if len(locations) == 0:
            messagebox.showerror("Error", "Please enter locations.")
            return

        keywords = keywords.split(",")
        locations = locations.split(",")

        if len(keywords) != len(locations):
            messagebox.showerror(
                "Error",
                "The number of business names should match the number of locations.",
            )
            return

        if not self.file_path:
            self.file_path = os.path.join(os.getcwd(), "datafile.csv")

        self.file_path = pathlib.Path(self.file_path).resolve()
        # confirm user the selected file path is the desired one with a popup
        file_path_confirmed = messagebox.askyesno(
            "Confirm File Path",
            f"Are you sure you want to save the data to {self.file_path.absolute()}?",
        )

        if not file_path_confirmed:
            return

        # create empty file
        pathlib.Path(self.file_path).touch()

        self.progress.set()
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal", fg_color="red")
        self.update()

        queries = list(zip(keywords, locations))

        scrape_thread = threading.Thread(
            target=self.run_scraping,
            args=(queries, self.file_path),
        )
        scrape_thread.start()

    async def run(self, query, progress, semaphore, proxy=None):
        BASE_HEADERS = {
            "accept-language": "en-US,en;q=0.9",
            "user-agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        }

        result_searchs = []
        async with aiohttp.ClientSession(
            headers=BASE_HEADERS,
            connector=aiohttp.TCPConnector(ssl=False),
        ) as session:
            try:
                search = self.mapper.get_search(self.website)

                if not search:
                    log.error(f"`search` method not implemented for {self.website}.")
                    self.stop_button.invoke()
                    sys.exit(1)

                search_result = await asyncio.gather(
                    *[
                        search(
                            keyword,
                            location=location,
                            session=session,
                            proxy=proxy,
                            progress=progress,
                            semaphore=semaphore,
                        )
                        for keyword, location in query
                        if progress.is_set()
                    ],
                )

                for result in search_result:
                    if isinstance(result, list):
                        result_searchs.extend(result)
            except Exception as e:
                log.error(e)

        return result_searchs

    def run_scraping(self, queries, file_location):
        self.loading_animation.start()

        proxy = Proxy(PROXY_FILE)
        start_time = time.perf_counter()
        semaphore = asyncio.Semaphore(10)  # Limit the number of concurrent requests
        result = asyncio.run(self.run(queries, self.progress, semaphore, proxy=proxy))

        scraped_data = [row for row in result if isinstance(row, dict)]

        if self.progress.is_set():
            self.stop_button.invoke()

        if scraped_data:
            self.save_to_csv(scraped_data, file_location)
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
        with open(file_location, "w", encoding="utf-8") as f:
            cw = csv.DictWriter(f, fieldnames=data[0].keys(), lineterminator="\n")
            cw.writeheader()
            cw.writerows(data)
