from __future__ import annotations

from motus.orient.specificity import DEFAULT_SPECIFICITY_WEIGHTS, specificity


def test_specificity_weights():
    assert specificity({"artifact": "chart"}) == DEFAULT_SPECIFICITY_WEIGHTS["artifact"]
    assert specificity({"theme": "dark"}) == DEFAULT_SPECIFICITY_WEIGHTS["theme"]
    assert specificity({"accessibility": "high"}) == DEFAULT_SPECIFICITY_WEIGHTS["accessibility"]
    assert specificity({"medium": "email"}) == DEFAULT_SPECIFICITY_WEIGHTS["medium"]


def test_specificity_unknown_keys_default_to_one():
    assert specificity({"unknown": "x"}) == 1
    assert specificity({"unknown": "x", "artifact": "chart"}) == 1 + DEFAULT_SPECIFICITY_WEIGHTS["artifact"]


def test_specificity_is_order_independent():
    a = specificity({"artifact": "chart", "theme": "dark"})
    b = specificity({"theme": "dark", "artifact": "chart"})
    assert a == b

