"""URL helpers.

Google Flights' raw booking-vendor data sometimes gives us a bare domain
(e.g. "www.lot.com/booking/xyz") with no "https://" scheme. Rendered as-is
in an <a href>, the browser treats that as a *relative* link off the
current page (e.g. "/flights/42" -> "/flights/www.lot.com/booking/xyz")
instead of an external site. Every booking URL is normalized through here
before it's stored or rendered so that never happens.
"""


def ensure_absolute_url(url: str | None) -> str | None:
    if not url:
        return url
    url = url.strip()
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("//"):
        return f"https:{url}"
    return f"https://{url}"
