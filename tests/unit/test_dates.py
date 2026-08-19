from datetime import date

from app.services.date_generator import generate_date_combinations


def test_generates_only_valid_date_pairs():
    pairs = list(generate_date_combinations(date(2026, 10, 29), date(2026, 11, 1), 13, 16, date(2026, 11, 16)))
    assert len(pairs) == 15
    assert pairs[0] == (date(2026, 10, 29), date(2026, 11, 11))
    assert pairs[-1] == (date(2026, 11, 1), date(2026, 11, 16))
    assert all((r - d).days in range(13, 17) and r <= date(2026, 11, 16) for d, r in pairs)
