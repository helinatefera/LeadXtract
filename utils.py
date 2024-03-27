import asyncio
import itertools
import random
import sys
import threading
import time
import typing
from collections import defaultdict

import aiohttp
from loguru import logger as log

from yellowpages.proxy import Proxy


async def make_request(
    async_session: aiohttp.ClientSession,
    url: str,
    semaphore: asyncio.Semaphore,
    proxy: Proxy | None = None,
    progress: threading.Event = None,
) -> str:
    """
    Make a request to the URL using the provided proxy. Retry the request if it fails.

    Args:
        async_session (aiohttp.ClientSession): Async session to make the request
        url (str): URL to make the request to
        proxy (Proxy): Proxy object to get the proxy from

    Returns:
        str: Response text from the URL
    """
    proxy = proxy or Proxy()
    async with semaphore:
        for _tries in range(3):
            if progress is None or not progress.is_set():
                return ""
            try:
                async with async_session.get(url=url, proxy=proxy.get()) as response:
                    if response.ok:
                        return await response.text()
                await asyncio.sleep(random.random())
            except Exception as err:
                log.error(f"Error making request: {err}")
                continue

        return ""


class SingletonMeta(type):
    """
    This is a metaclass for creating singleton classes.
    It ensures that only one instance of the singleton class can exist.
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


# creare write (singleton) which accept a widget two


class EventManager(metaclass=SingletonMeta):
    """
    This class is a singleton class that manages events and listeners.
    It allows subscribing to events, emitting events, and unsubscribing from events.
    """

    def __init__(self):
        self.listeners = defaultdict(
            list
        )  # Dictionary to store listeners for each event type

    def subscribe(self, event_type: str, listener: callable) -> None:
        """
        Subscribe to an event.

        Args:
            event_type (str): Type of event to subscribe to
            listener (callable): Listener function to call when the event is emitted

        Returns:
            None
        """
        self.listeners[event_type].append(listener)

    def emit(self, event_type: str, *args: typing.Any, **kwargs: typing.Any) -> None:
        """
        Emit an event.

        Args:
            event_type (str): Type of event to emit
            data (Any): Data to pass to the listeners

        Returns:
            None
        """
        if event_type in self.listeners:
            for listener in self.listeners[event_type]:
                listener(*args, **kwargs)

    def unsubscribe(self, event_type: str, listener: callable) -> None:
        """
        Unsubscribe from an event.

        Args:
            event_type (str): Type of event to unsubscribe from
            listener (callable): Listener function to unsubscribe

        Returns:
            None
        """
        if event_type in self.listeners:
            self.listeners[event_type].remove(listener)


class LoadingAnimation:

    def __init__(self, progress: threading.Event) -> None:
        self.progress = progress  # Event to stop the animation
        self.total_scraped = 0
        event_manager = EventManager()
        event_manager.subscribe("update_total", self.update)

    def start(self) -> None:
        """
        Start the loading animation.

        Args:
            progress (threading.Event): Event to stop the animation

        Returns:
            None
        """

        def animate() -> None:
            for icon in itertools.cycle(["⠯", "⠟", "⠻", "⠽", "⠾", "⠷"]):
                if not self.progress.is_set():
                    self._stop()
                    return

                sys.stdout.write(
                    "\r🔘 Scraping in progress... Total scraped: %(total)d %(icon)s%(spaces)s"
                    % {
                        "total": self.total_scraped,
                        "icon": icon,
                        "spaces": " " * 0,
                    }
                )
                sys.stdout.flush()
                time.sleep(0.1)
                # print("SOMETHING")

        self.process = threading.Thread(target=animate, daemon=True)
        self.process.start()

    def _stop(self):
        """
        Stop the loading animation.

        Args:
            total (int): Total number of items scraped

        Returns:
            None
        """
        self.progress.clear()  # Set the event to stop the animation
        sys.stdout.write(
            "\r🔘 Scraping stoped. Total scraped: %(total)d%(spaces)s"
            % {
                "total": self.total_scraped,
                "spaces": " " * 10,
            }
        )
        sys.stdout.flush()
        self.total_scraped = 0

    def update(self, value: int):
        """
        Update the total number of items scraped.

        Args:
            total (int): Total number of items scraped

        Returns:
            None
        """
        self.total_scraped += value
