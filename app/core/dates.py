from datetime import date


def format_date(value: date) -> str:
    return value.strftime("%d %b %Y")


def format_duration(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"
