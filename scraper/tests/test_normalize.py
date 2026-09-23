from datetime import datetime, timedelta, timezone

import pytest

from hunter.models import Listing
from hunter.normalize import (
    normalize, parse_bedrooms, parse_number, parse_phone, parse_posted, parse_price, parse_size, whatsapp_link,
)
from hunter.zones import match_zone


@pytest.mark.parametrize("raw,expected", [
    ("350.000", 350000), ("350,000", 350000), ("1.200.000", 1200000), ("1,250.50", 1250.5),
    ("650", 650), ("1.250,50", 1250.5), ("12,5", 12.5),
])
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


@pytest.mark.parametrize("text,expected", [
    ("₡350.000", (350000, "CRC")),
    ("₡ 350,000 mensuales", (350000, "CRC")),
    ("¢340.000", (340000, "CRC")),
    ("CRC 300000", (300000, "CRC")),
    ("350 mil colones", (350000, "CRC")),
    ("₡350k", (350000, "CRC")),
    ("$650", (650, "USD")),
    ("US$ 1,200", (1200, "USD")),
    ("USD 700 por mes", (700, "USD")),
    ("650 dólares", (650, "USD")),
    ("$690/mes", (690, "USD")),
    ("Precio: 325000", (325000, "CRC")),
    ("800", (800, "USD")),
])
def test_parse_price(text, expected):
    assert parse_price(text) == expected


def test_parse_price_does_not_take_bedroom_count_from_free_text():
    assert parse_price("Apartamento 2 habitaciones en Zapote", allow_bare=False) is None


def test_price_does_not_swallow_following_numbers():
    assert parse_price("₡350.000 2 habitaciones") == (350000, "CRC")


@pytest.mark.parametrize("text,expected", [
    ("2 habitaciones", 2), ("3 hab.", 3), ("dos habitaciones y un baño", 2), ("Estudio amueblado", 0),
    ("sin datos", None), ("1 dormitorio", 1),
])
def test_bedrooms(text, expected):
    assert parse_bedrooms(text) == expected


def test_size_and_phone():
    assert parse_size("Apartamento de 65 m2") == 65
    assert parse_size("85 metros cuadrados") == 85
    assert parse_phone("Llamar al 2222-3333 o WhatsApp +506 8765 4321") == "87654321"
    assert parse_phone("Tel 2222-3333") == "22223333"
    assert parse_phone("sin teléfono") is None
    assert whatsapp_link("87654321", "Hola") == "https://wa.me/50687654321?text=Hola"


def test_parse_posted():
    now = datetime(2026, 9, 23, 12, tzinfo=timezone.utc)
    assert parse_posted("hace 2 horas", now) == now - timedelta(hours=2)
    assert parse_posted("Publicado hace 3 días", now) == now - timedelta(days=3)
    assert parse_posted("ayer", now) == now - timedelta(days=1)
    assert parse_posted("20/09/2026", now) == datetime(2026, 9, 20, tzinfo=timezone.utc)
    assert parse_posted("2026-09-21T08:30:00", now) == datetime(2026, 9, 21, 8, 30, tzinfo=timezone.utc)
    assert parse_posted("", now) is None


@pytest.mark.parametrize("text,zone", [
    ("San Pedro de Montes de Oca", "Montes de Oca"),
    ("Los Yoses", "Montes de Oca"),
    ("Granadilla, Curridabat", "Curridabat"),
    ("La Unión, Cartago", "Tres Ríos"),
    ("San Francisco de Dos Rios", "San Francisco de Dos Ríos"),
    ("San Antonio de Desamparados", "San Antonio de Desamparados"),
    ("ZAPOTE", "Zapote"),
    ("Escazú", None),
])
def test_zones(text, zone):
    assert match_zone(text) == zone


def test_normalize_usd_listing():
    item = normalize(Listing(site="x", listing_id="1", url="u", title="Apto 2 habitaciones",
                             price_raw="$700", location_text="Zapote"), usd_crc_rate=500)
    assert (item.price, item.currency, item.price_crc) == (700, "USD", 350000)
    assert item.bedrooms == 2 and item.zone == "Zapote"
