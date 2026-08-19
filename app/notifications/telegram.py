import httpx

from app.core.config import settings
from app.notifications.base import NotificationProvider


class TelegramNotificationProvider(NotificationProvider):
    """Minimal Telegram Bot API sender; tokens remain only in environment variables."""

    async def send_price_alert(self, message: str, booking_url: str | None = None) -> None:
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            raise RuntimeError("Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
        payload = {"chat_id": settings.telegram_chat_id, "text": message, "disable_web_page_preview": True}
        if booking_url:
            payload.update({"reply_markup": {"inline_keyboard": [[{"text": "Open flight", "url": booking_url}]]}})
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload)
        response.raise_for_status()
