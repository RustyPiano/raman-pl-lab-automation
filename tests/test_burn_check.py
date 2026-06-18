import pytest

from lab_auto.processing.burn_check import compare_spectra


def test_identical_spectra_zero_deviation_not_burned():
    a = [10.0, 20.0, 30.0, 40.0]
    result = compare_spectra(a, list(a), metric="relative_l2", threshold=0.1)
    assert result["deviation"] == pytest.approx(0.0)
    assert result["burned"] is False


def test_large_change_flags_burned():
    a = [10.0, 20.0, 30.0, 40.0]
    b = [1.0, 2.0, 3.0, 4.0]
    result = compare_spectra(a, b, metric="relative_l2", threshold=0.1)
    assert result["deviation"] > 0.1
    assert result["burned"] is True


def test_small_change_below_threshold_not_burned():
    a = [100.0, 100.0, 100.0]
    b = [100.5, 99.5, 100.0]
    result = compare_spectra(a, b, metric="relative_l2", threshold=0.1)
    assert result["deviation"] < 0.1
    assert result["burned"] is False


def test_deviation_is_relative_l2():
    a = [3.0, 4.0]  # ||a|| = 5
    b = [0.0, 0.0]
    result = compare_spectra(a, b, metric="relative_l2", threshold=2.0)
    # ||a-b|| / (||a|| + eps) ~= 5 / 5 = 1.0
    assert result["deviation"] == pytest.approx(1.0, abs=1e-6)
    assert result["burned"] is False  # threshold 2.0 not exceeded


def test_length_mismatch_raises():
    with pytest.raises(ValueError):
        compare_spectra([1.0, 2.0], [1.0], metric="relative_l2", threshold=0.1)


def test_unknown_metric_raises():
    with pytest.raises(ValueError):
        compare_spectra([1.0], [1.0], metric="cosine", threshold=0.1)


def test_threshold_boundary_is_not_burned():
    # deviation exactly at threshold should not flag (strict >)
    a = [3.0, 4.0]
    b = [0.0, 0.0]
    result = compare_spectra(a, b, metric="relative_l2", threshold=1.0)
    assert result["deviation"] == pytest.approx(1.0, abs=1e-6)
    assert result["burned"] is False
