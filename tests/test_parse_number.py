from tools._playwright_scraper import _parse_number


def test_plain_float():
    assert _parse_number("84.23") == 84.23


def test_positive_sign_and_percent():
    assert _parse_number("+56.88%") == 56.88


def test_negative_percent():
    assert _parse_number("-3.5%") == -3.5


def test_millions():
    assert _parse_number("24.89M") == 24_890_000.0


def test_billions():
    assert _parse_number("6.33B") == 6_330_000_000.0


def test_thousands():
    assert _parse_number("1.5K") == 1_500.0


def test_commas():
    assert _parse_number("72,239,400") == 72_239_400.0


def test_dash_returns_none():
    assert _parse_number("--") is None


def test_na_returns_none():
    assert _parse_number("N/A") is None


def test_empty_string_returns_none():
    assert _parse_number("") is None


def test_whitespace_returns_none():
    assert _parse_number("   ") is None


def test_garbage_returns_none():
    assert _parse_number("abc") is None
