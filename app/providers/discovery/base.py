from typing import Protocol


class DiscoveryProvider(Protocol):
    def search(self, query: object) -> list[object]: ...
