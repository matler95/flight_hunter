from typing import Protocol


class VerificationProvider(Protocol):
    def verify(self, flight: object) -> object: ...
