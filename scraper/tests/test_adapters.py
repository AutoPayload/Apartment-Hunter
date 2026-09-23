import pytest

from hunter.adapters import ADAPTERS, get_adapter
from hunter.models import Listing


@pytest.mark.parametrize("site,count", [
    ("encuentra24", 5), ("casas24", 2), ("anuntico", 2), ("inhauscr", 2), ("alquilacr", 2),
])
def test_each_adapter_parses_its_fixture(site, count, fixture_html):
    adapter = get_adapter(site)
    listings = adapter.parse(fixture_html(f"{site}.html"), adapter.urls()[0])
    assert len(listings) == count
    for item in listings:
        assert item.site == site
        assert item.url.startswith("https://")
        assert item.listing_id and item.title
    assert len({item.listing_id for item in listings}) == count


def test_encuentra24_fields(fixture_html):
    adapter = get_adapter("encuentra24")
    first = adapter.parse(fixture_html("encuentra24.html"), adapter.urls()[0])[0]
    assert first.listing_id == "31000001"
    assert first.price_raw == "₡340.000"
    assert first.location_text == "Curridabat, San José"
    assert first.photos == ["https://photos.encuentra24.com/t/31000001-1.jpg"]  # data: placeholder skipped
    assert first.posted_at is not None
    assert "seguridad" in first.description


def test_json_ld_path(fixture_html):
    adapter = get_adapter("casas24")
    items = {i.listing_id: i for i in adapter.parse(fixture_html("casas24.html"), adapter.urls()[0])}
    item = items["900111"]
    assert item.price_raw == "CRC 340000"
    assert "Curridabat" in item.location_text
    assert item.photos == ["https://img.casas24.com/900111/1.jpg"]


def test_anuntico_ids_and_dates(fixture_html):
    adapter = get_adapter("anuntico")
    items = adapter.parse(fixture_html("anuntico.html"), adapter.urls()[0])
    assert [i.listing_id for i in items] == ["7712345", "7712346"]
    assert items[0].posted_at.day == 20


def test_detail_page_enrichment(fixture_html):
    adapter = get_adapter("encuentra24")
    item = Listing(site="encuentra24", listing_id="31000001", url="https://www.encuentra24.com/x/31000001",
                   title="t", description="corto", photos=["https://photos.encuentra24.com/t/31000001-1.jpg"])
    item = adapter.parse_detail(fixture_html("encuentra24_detail.html"), item)
    assert "Agua incluida" in item.description
    assert item.phone == "88887777"
    assert "https://photos.encuentra24.com/f/31000001-2.jpg" in item.photos
    assert len(item.photos) == 3


def test_url_override_from_env(monkeypatch):
    monkeypatch.setenv("HUNTER_URLS_ANUNTICO", "https://a.example/1 https://a.example/2")
    assert get_adapter("anuntico").urls() == ["https://a.example/1", "https://a.example/2"]


def test_all_adapters_registered():
    assert set(ADAPTERS) == {"encuentra24", "casas24", "anuntico", "inhauscr", "alquilacr"}
