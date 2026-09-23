from hunter.extract.keywords import KeywordExtractor
from hunter.models import Extraction, Listing
from hunter.normalize import normalize
from hunter.scoring import score


def make(price_raw="₡340.000", zone="Curridabat", desc="", title="Apartamento"):
    return normalize(Listing(site="t", listing_id="1", url="u", title=title, price_raw=price_raw,
                             location_text=zone, description=desc), usd_crc_rate=505)


def ex(**kw):
    base = dict(parking="yes", unit_type="apartment", zone="Curridabat")
    return Extraction(**{**base, **kw})


def test_tier_a():
    r = score(make(), ex())
    assert r.tier == "A" and r.score >= 70


def test_room_rejected():
    assert score(make(), ex(unit_type="room")).tier == "reject"


def test_no_parking_rejected():
    assert score(make(), ex(parking="no")).tier == "reject"


def test_unknown_parking_is_tier_b():
    r = score(make(), ex(parking="unknown"))
    assert r.tier == "B" and "parqueo sin confirmar" in r.reasons[0]


def test_between_350_and_380_is_tier_b():
    assert score(make("₡370.000"), ex()).tier == "B"


def test_over_380_is_none():
    assert score(make("₡390.000"), ex()).tier == "none"


def test_boundaries():
    assert score(make("₡350.000"), ex()).tier == "A"
    assert score(make("₡380.000"), ex()).tier == "B"


def test_outside_zone_is_none():
    assert score(make(zone="Escazú"), ex(zone=None)).tier == "none"


def test_usd_converted_before_scoring():
    r = score(make("$690"), ex())  # 690 * 505 = 348,450
    assert r.tier == "A" and any("USD" in x for x in r.reasons)


def test_bonus_points():
    plain = score(make(), ex()).score
    extra = score(make(), ex(security="yes", pets="yes", utilities_included="yes", pool_gym="yes")).score
    assert extra > plain


def test_missing_price_in_zone_goes_to_digest():
    assert score(make(price_raw=""), ex()).tier == "B"


def test_keyword_extractor_rules():
    k = KeywordExtractor()
    e = k.extract(make(desc="Condominio con seguridad 24/7, 1 parqueo, acepta mascotas, agua incluida"))
    assert (e.parking, e.security, e.pets, e.utilities_included) == ("yes", "yes", "yes", "yes")
    e = k.extract(make(desc="2 habitaciones, sin parqueo, no se aceptan mascotas"))
    assert (e.parking, e.pets) == ("no", "no")
    e = k.extract(make(title="Se alquila habitación en Sabanilla", desc="cocina compartida"))
    assert e.unit_type == "room"
    e = k.extract(make(title="Estudio en San Pedro"))
    assert e.unit_type == "studio"
