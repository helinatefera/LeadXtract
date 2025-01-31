import os

import customtkinter as ctk
from decouple import config
from licensing.methods import Helpers, Key
from loguru import logger as log
from yellowpages import YellowPagesScraperUI

# Remove default loguru logger and configure it
log.remove()
# log.add(sys.stdout, level="ERROR", format="{message} {file} {line}")

RSAPubKey = config("RSA_PUB_KEY", default="") or config("RSA_PUB_KEY", default="")

auth = config("AUTH_TOKEN", default="")
key_file = config("KEY_FILE", default="key.txt")


def get_saved_key():
    if os.path.exists(key_file):
        with open(key_file, "r") as file:
            return file.read().strip()
    return None


def save_key(key):
    with open(key_file, "w") as file:
        file.write(key)


def display_result(message, title="Result"):
    root = ctk.CTk()
    root.title("Yellow Pages Scraper v1.0")
    # root.iconbitmap(resource_path('icon.ico'))
    root.config(bg="#f9c852")
    # Set the window size and position
    window_width = 370
    window_height = 153

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    position_top = int(screen_height / 2 - window_height / 2)
    position_right = int(screen_width / 2 - window_width / 2)

    root.geometry(f"{window_width}x{window_height}+{position_right}+{position_top}")

    result_label = ctk.CTkLabel(
        root, text=message, font=("Helvetica", 15, "bold"), wraplength=350
    )
    result_label.pack(pady=30)
    result_label.configure(bg_color="black", fg_color="#f9c852")
    close_button = ctk.CTkButton(
        root, text="Close", command=root.destroy, font=("Helvetica", 16)
    )
    close_button.configure(fg_color="red", text_color="white")
    close_button.pack(pady=10)
    root.mainloop()


def activate_key():
    key = entry.get()
    result = Key.activate(
        token=auth,
        rsa_pub_key=RSAPubKey,
        product_id=26728,
        key=key,
        machine_code=Helpers.GetMachineCode(v=2),
    )
    print(result)
    if result[0] is None:
        custom_message = "An error occurred while activating the license."
        if result[1] == "429":
            custom_message = "Too many requests. Please try again later."
        elif result[1] == "404":
            custom_message = "License not found. Please check your key."
        elif result[1] == "403":
            custom_message = "License is not valid. Please use a valid key."
        display_result(custom_message, "Activation Error")
    elif not Helpers.IsOnRightMachine(result[0], v=2):
        display_result(
            "This license is already activated on another machine.", "Activation Error"
        )
    else:
        display_result("The license is valid!", "Activation Success")
        save_key(key)  # Save the activation key
        root.quit()  # Close the key entry window
        app = YellowPagesScraperUI()
        app.mainloop()


saved_key = get_saved_key()
print(f"Saved key: {saved_key}")
if saved_key:
    # Attempt to activate with the saved key
    result = Key.activate(
        token=auth,
        rsa_pub_key=RSAPubKey,
        product_id=26728,
        key=saved_key,
        machine_code=Helpers.GetMachineCode(v=2),
    )
    print(result)

    if result[0] is None or not Helpers.IsOnRightMachine(result[0], v=2):
        saved_key = None  # Key is invalid, reset saved_key

if saved_key is not None:
    # License is already activated, start the application
    app = YellowPagesScraperUI()
    app.mainloop()
else:
    # License is not activated or the saved key is invalid, show the Tkinter window
    root = ctk.CTk(fg_color="#f9c852")

    window_width = 500
    window_height = 200

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    position_top = int(screen_height / 2 - window_height / 2)
    position_right = int(screen_width / 2 - window_width / 2)

    root.geometry(f"{window_width}x{window_height}+{position_right}+{position_top}")

    root.resizable(False, False)  # Disable window resizing
    # root.iconbitmap(resource_path("icon.ico"))
    root.title("License Key Activation")

    # Create and place the key entry field
    label = ctk.CTkLabel(
        root,
        text="Enter your license key:",
        font=("Arial", 20, "bold"),
        corner_radius=0,
    )
    label.pack(padx=10, pady=15, fill="x")

    entry = ctk.CTkEntry(root, corner_radius=0)
    entry.pack(padx=15, pady=5, fill="x", ipady=10)

    # Create and place the activate button
    button = ctk.CTkButton(
        root, text="ACTIVATE", command=activate_key, fg_color="green", corner_radius=0
    )
    button.pack(pady=(10, 5), ipady=10)
    # Run the Tkinter event loop
    root.mainloop()
