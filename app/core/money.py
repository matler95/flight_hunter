from decimal import Decimal


def format_money(amount: Decimal | float, currency: str) -> str:
    return f"{Decimal(amount):,.0f} {currency}".replace(",", " ")
