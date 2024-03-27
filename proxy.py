import pathlib
import random
import re


class Proxy:
    def __init__(self, file_path: str = None) -> None:
        """
        Proxy class to handle the proxy list from a file, format the proxy
        and return a random proxy from the list.

        Args:
            file_path (str): Path to the file containing the proxy list.

        Returns:
            None
        """

        # Path to the file containing the proxy list
        self.file_path: str = file_path
        # List of proxies if the file exists
        self._proxy_list: list | None = self._get_proxies()
        # Total number of proxies in the list
        self.total: int = len(self._proxy_list or [])
        self.current = 0  # Current index of the proxy list

    def _get_proxies(self) -> list | None:
        """
        Get the list of proxies from the file. format the proxy into
        socks5://username:password@ip:port and shuffle the list.

        Args:
            None

        Returns:
            list | None: List of proxies if the file exists, None otherwise.
        """

        # Check if the file exists
        if self.file_path and pathlib.Path(self.file_path).exists():
            with open(self.file_path, "r") as file:
                # Read the file and format the proxy
                proxies = [
                    self._format_proxy(line.strip()) for line in file.readlines()
                ]
                random.shuffle(proxies)
                return proxies
        return

    def _format_proxy(self, proxy: str) -> str:
        """
        Format the proxy into socks5://username:password@ip:port

        Args:
            proxy (str): Proxy string in the format ip:port:username:password

        Returns:
            str: Formatted proxy string
        """

        # Check if the proxy is in the format ip:port:username:password
        pattern = r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+):(\w+):(\w+)"
        match = re.match(pattern, proxy)
        if match:
            ip, port, username, password = match.groups()
            return f"socks5://{username}:{password}@{ip}:{port}"
        return proxy

    def get(self) -> str | None:
        """
        Get a random proxy from the list.

        Args:
            None

        Returns:
            str | None: Random proxy from the list if it exists
                        None otherwise.
        """

        if self._proxy_list is not None:
            # Get the next proxy from the list
            proxy = self._proxy_list[self.current % self.total]
            self.current += 1
            return proxy

        return
