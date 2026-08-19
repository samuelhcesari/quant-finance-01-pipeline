"""Test de _clean_numeric (sql/analytics/visualize.py) : NULL SQL, +/-inf et
valeurs non numériques doivent tous devenir NaN pandas, jamais une valeur
inventée à la place (ex. 0)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from financial_intelligence.analytics.visualize import _clean_numeric


def test_clean_numeric_converts_none_to_nan():
    result = _clean_numeric(pd.Series([1.0, None, 2.0]))
    assert result.isna().sum() == 1
    assert list(result.dropna()) == [1.0, 2.0]


def test_clean_numeric_converts_inf_to_nan():
    result = _clean_numeric(pd.Series([1.0, np.inf, -np.inf, 2.0]))
    assert result.isna().sum() == 2
    assert list(result.dropna()) == [1.0, 2.0]


def test_clean_numeric_leaves_finite_values_untouched():
    result = _clean_numeric(pd.Series([-3.5, 0.0, 42.1]))
    assert list(result) == [-3.5, 0.0, 42.1]
