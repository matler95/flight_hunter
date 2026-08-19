from typing import Protocol


class NotificationChannel(Protocol):
    def send(self, message: str) -> None: ...
