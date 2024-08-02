from . import austria  # noqa: F401
from . import belgium  # noqa: F401
from . import canada  # noqa: F401
from . import germany  # noqa: F401
from . import ireland  # noqa: F401
from . import italy  # noqa: F401
from . import nicaragua  # noqa: F401
from . import south_africa  # noqa: F401
from . import switzerland  # noqa: F401
from . import usa  # noqa: F401


class Mapper:

    def __init__(self) -> None:
        self.mapping = {
            "austria": (austria, False),
            "belgium": (belgium, False),
            "canada": (canada, True),
            "germany": (germany, False),
            "ireland": (ireland, False),
            "italy": (italy, False),
            "nicaragua": (nicaragua, False),
            "switzerland": (switzerland, False),
            "south_africa": (south_africa, False),
            "USA": (usa, False),
        }

    def get_search(self, country):
        country = country.lower().replace(" ", "_")
        module, _ = self.mapping.get(country)
        if "search" in dir(module):
            return module.search
        return None

    def get_options(self):
        return list(
            map(lambda k: k.replace("_", " ").capitalize(), self.mapping.keys())
        )

    def get_dropdown(self, country):
        country = country.lower().replace(" ", "_")
        _, dropdown = self.mapping.get(country, (None, False))
        if dropdown:
            return self.mapping[country][0].DROPDOWN_OPTIONS
        return dropdown
