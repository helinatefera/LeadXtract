from distutils.core import setup
import py2exe

setup(
    options={
        "py2exe": {
            "packages": ["requests", "beautifulsoup4", "customtkinter"],
            "includes": ["math", "random", "re", "csv", "tkinter", "threading"],
            "dll_excludes": ["MSVCP90.dll"],  # Exclude DLL that might cause issues
        }
    },
    windows=[  # Use "windows" for GUI applications; replace "your_script_name.py" with your script's filename
        {
            "script": "main.py"
        }
    ],
    zipfile=None,  # Put everything in the .exe instead of a zip file
)
