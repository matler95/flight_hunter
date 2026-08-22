from app.core.urls import ensure_absolute_url


def test_bare_domain_gets_https_scheme():
    assert ensure_absolute_url("www.lot.com/booking/mock") == "https://www.lot.com/booking/mock"


def test_already_absolute_url_is_left_untouched():
    assert ensure_absolute_url("https://www.lot.com/booking/mock") == "https://www.lot.com/booking/mock"
    assert ensure_absolute_url("http://example.com/x") == "http://example.com/x"


def test_protocol_relative_url_gets_https():
    assert ensure_absolute_url("//www.lot.com/booking") == "https://www.lot.com/booking"


def test_none_and_empty_pass_through():
    assert ensure_absolute_url(None) is None
    assert ensure_absolute_url("") == ""
