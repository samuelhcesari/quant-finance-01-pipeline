"""Tests unitaires d'evaluate_rule/evaluate_profile, en isolation, sans base
de données — la sémantique des règles YAML est une fonction pure.
"""

from __future__ import annotations

import pytest

from financial_intelligence.analytics.screening_engine import evaluate_profile, evaluate_rule


@pytest.mark.parametrize(
    "operator,value,threshold,expected",
    [
        (">=", 10, 5, True),
        (">=", 5, 5, True),
        (">=", 4, 5, False),
        ("<=", 5, 10, True),
        ("<=", 11, 10, False),
        (">", 6, 5, True),
        (">", 5, 5, False),
        ("<", 4, 5, True),
        ("==", 5, 5, True),
        ("==", 5, 6, False),
        ("!=", 5, 6, True),
    ],
)
def test_evaluate_rule_operators(operator, value, threshold, expected):
    rule = {"metric": "x", "operator": operator, "threshold": threshold, "allow_null": False}
    assert evaluate_rule(rule, {"x": value}) is expected


def test_evaluate_rule_missing_value_allow_null_true_is_satisfied():
    rule = {"metric": "ev_to_ebitda", "operator": "<=", "threshold": 12.0, "allow_null": True}
    assert evaluate_rule(rule, {"ev_to_ebitda": None}) is True


def test_evaluate_rule_missing_value_allow_null_false_is_not_satisfied():
    """Donnée manquante traitée comme un échec explicite, pas comme un succès
    par défaut."""
    rule = {"metric": "revenue_growth", "operator": ">=", "threshold": 0.15, "allow_null": False}
    assert evaluate_rule(rule, {"revenue_growth": None}) is False


def test_evaluate_rule_missing_value_default_allow_null_is_false():
    rule = {"metric": "revenue_growth", "operator": ">=", "threshold": 0.15}  # allow_null absent
    assert evaluate_rule(rule, {"revenue_growth": None}) is False


def test_evaluate_profile_passes_when_all_rules_satisfied():
    profile = {
        "min_score": 1.0,
        "rules": [
            {"metric": "revenue_growth", "operator": ">=", "threshold": 0.15, "allow_null": False},
            {"metric": "net_debt_to_ebitda", "operator": "<=", "threshold": 4.0, "allow_null": False},
        ],
    }
    row = {"revenue_growth": 0.20, "net_debt_to_ebitda": 2.0}
    passed, score = evaluate_profile(profile, row)
    assert passed is True
    assert score == 1.0


def test_evaluate_profile_fails_when_one_rule_unsatisfied_and_min_score_is_strict():
    profile = {
        "min_score": 1.0,
        "rules": [
            {"metric": "revenue_growth", "operator": ">=", "threshold": 0.15, "allow_null": False},
            {"metric": "net_debt_to_ebitda", "operator": "<=", "threshold": 4.0, "allow_null": False},
        ],
    }
    row = {"revenue_growth": 0.05, "net_debt_to_ebitda": 2.0}  # échoue la 1re règle
    passed, score = evaluate_profile(profile, row)
    assert passed is False
    assert score == 0.5


def test_evaluate_profile_partial_min_score_allows_lenient_pass():
    profile = {
        "min_score": 0.5,
        "rules": [
            {"metric": "a", "operator": ">=", "threshold": 1, "allow_null": False},
            {"metric": "b", "operator": ">=", "threshold": 1, "allow_null": False},
        ],
    }
    row = {"a": 1, "b": 0}  # seule la moitié des règles passe
    passed, score = evaluate_profile(profile, row)
    assert score == 0.5
    assert passed is True  # min_score=0.5 -> suffisant


def test_evaluate_profile_empty_rules_does_not_crash():
    profile = {"min_score": 1.0, "rules": []}
    passed, score = evaluate_profile(profile, {})
    assert score == 0.0
