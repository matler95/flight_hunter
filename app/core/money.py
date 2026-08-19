from decimal import Decimal


def format_money(amount: Decimal, currency: str) -> str:
    return f"{amount:.2f} {currency}"
