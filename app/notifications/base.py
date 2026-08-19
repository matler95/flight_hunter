from abc import ABC, abstractmethod


class NotificationProvider(ABC):
    @abstractmethod
    async def send_price_alert(self, message: str, booking_url: str | None = None) -> None:
        """Deliver a price alert without logging credentials."""
