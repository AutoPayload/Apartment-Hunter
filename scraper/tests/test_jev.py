"""Jev extractor against a fake client (no network)."""

from types import SimpleNamespace

from hunter.extract.jev import JevExtractor
from hunter.models import Listing
from hunter.normalize import normalize


def choice(value, confidence):
    return SimpleNamespace(choice=value, confidence=confidence)


class FakeClient:
    def __init__(self, choices=None, nouls=None, fail=False):
        self.choices, self.nouls, self.fail = choices or {}, nouls or {}, fail
        self.calls = []

    def system_one(self, state, questions, **kw):
        self.calls.append((state, questions))
        if self.fail:
            raise RuntimeError("boom")
        return SimpleNamespace(choices=self.choices, nouls=self.nouls)


def listing(desc=""):
    return normalize(Listing(site="t", listing_id="1", url="u", title="Apartamento", price_raw="₡340.000",
                             location_text="", description=desc), 505)


def test_confident_answers_used_and_unsure_become_unknown():
    client = FakeClient({
        "parking": choice("yes", 0.95), "unit_type": choice("apartment", 0.9),
        "pets": choice("yes", 0.4),  # below cutoff
        "zone": choice("Zapote", 0.85), "security": choice("unknown", 0.9),
    })
    ex = JevExtractor("k", min_confidence=0.6, client=client).extract(listing())
    assert ex.parking == "yes" and ex.unit_type == "apartment"
    assert ex.pets == "unknown"
    assert ex.zone == "Zapote"
    assert ex.source == "jev" and ex.confidence["pets"] == 0.4
    questions = client.calls[0][1]
    assert set(questions) >= {"parking", "unit_type", "pets", "security", "utilities_included", "zone"}


def test_keywords_fill_what_jev_leaves_unknown():
    client = FakeClient({"parking": choice("unknown", 0.9)})
    ex = JevExtractor("k", client=client).extract(listing("2 habitaciones, sin parqueo"))
    assert ex.parking == "no"


def test_falls_back_to_keywords_on_error():
    ex = JevExtractor("k", client=FakeClient(fail=True)).extract(listing("con parqueo"))
    assert ex.source == "keywords" and ex.parking == "yes"


def test_other_zone_is_not_a_target():
    client = FakeClient({"zone": choice("other", 0.99)})
    assert JevExtractor("k", client=client).extract(listing()).zone is None


def test_same_listing():
    client = FakeClient(nouls={"same": SimpleNamespace(noul=0.91)})
    assert JevExtractor("k", client=client).same_listing("a", "b") == 0.91
    assert JevExtractor("k", client=FakeClient(fail=True)).same_listing("a", "b") is None


def test_real_sdk_question_objects_build():
    from hunter.extract.jev import _questions

    qs = _questions()
    assert qs["parking"].model_dump()["type"] == "choice"
    assert "Curridabat" in qs["zone"].criteria
