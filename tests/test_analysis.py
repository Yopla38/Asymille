"""The operations: each on a curve whose answer is known."""
from __future__ import annotations

import math

import numpy as np
import pytest

from asymille import analysis
from asymille.analysis import AnalysisError, run

X = np.linspace(0, 10, 1001)


def col(out: dict, name: str) -> np.ndarray:
    return np.array([np.nan if v is None else v for v in next(c for c in out["columns"] if c["name"] == name)["values"]], float)


def fact(out: dict, label: str) -> dict:
    return next(f for f in out["facts"] if f["label"].startswith(label))


def test_every_operation_runs_and_says_what_it_did() -> None:
    rng = np.random.default_rng(0)
    y = np.exp(-(X - 4) ** 2 / 0.5) + 0.3 * np.sin(X) + rng.normal(0, 0.01, X.size)
    described = analysis.described()
    assert len(described) == len(analysis.REGISTRY) >= 17 and all(o["summary"] and o["family"] in analysis.FAMILIES for o in described)
    for op in described:
        out = run(op["name"], X, y, {}, *((X, y) if op["second"] else ()))
        assert out["note"].endswith(".") and (out["columns"] or out["facts"]), op["name"]
        for c in out["columns"]:
            assert len(c["values"]) == (len(X) if out["sheet"] == "same" else len(out["columns"][0]["values"])), op["name"]


def test_smoothing_lowers_the_noise_and_keeps_the_peak() -> None:
    rng = np.random.default_rng(1)
    clean = np.exp(-(X - 5) ** 2 / (2 * 0.4 ** 2))
    noisy = clean + rng.normal(0, 0.05, X.size)
    for name, args in (("smooth_savgol", {"window": 41, "order": 3}), ("smooth_moving", {"window": 15}), ("smooth_gaussian", {"sigma": 6}), ("smooth_median", {"window": 15}),
                       ("fft_filter", {"kind": "low", "cutoff": 0.05})):
        smooth = col(run(name, X, noisy, args), "Filtered" if name == "fft_filter" else "Smoothed")
        assert np.std(smooth - clean) < 0.4 * np.std(noisy - clean), name
        assert smooth.max() == pytest.approx(1, abs=0.06), name


def test_derivative_and_integral_of_known_functions() -> None:
    assert col(run("differentiate", X, np.sin(X)), "dy/dx")[5:-5] == pytest.approx(np.cos(X)[5:-5], abs=2e-5)
    assert col(run("differentiate", X, X ** 3, {"order": "2"}), "d2y/dx2")[5:-5] == pytest.approx(6 * X[5:-5], abs=1e-3)
    uneven = np.sort(np.random.default_rng(2).uniform(0, 3, 400))
    assert col(run("differentiate", uneven, uneven ** 2), "dy/dx")[1:-1] == pytest.approx(2 * uneven[1:-1], abs=1e-9)        # exact for a parabola, even spacing or not
    out = run("integrate", X, np.sin(X))
    assert col(out, "Integral") == pytest.approx(1 - np.cos(X), abs=2e-5) and fact(out, "Area")["value"] == pytest.approx(1 - math.cos(10), abs=2e-5)       # the trapezoid rule, h = 0.01
    gauss = 3 * np.exp(-(X - 5) ** 2 / (2 * 0.3 ** 2)) + 2 + 0.1 * X
    above = run("integrate", X, gauss, {"baseline": "ends"})
    assert fact(above, "Area")["value"] == pytest.approx(3 * 0.3 * math.sqrt(2 * math.pi), rel=1e-4) and fact(above, "Centroid")["value"] == pytest.approx(5, abs=1e-6)


def test_rows_that_are_not_numbers_stay_empty_and_order_is_kept() -> None:
    x, y = np.array([3.0, 1.0, np.nan, 2.0, 4.0]), np.array([9.0, 1.0, 5.0, np.nan, 16.0])
    values = run("integrate", x, y)["columns"][0]["values"]
    assert values[2] is None and values[3] is None and values[1] == 0 and values[0] == pytest.approx(10) and values[4] == pytest.approx(22.5)
    with pytest.raises(AnalysisError, match="at least 2 points"):
        run("integrate", [1, None, 3], [None, 2, None])


@pytest.mark.parametrize("name, args", [("baseline_als", {"smoothness": 6, "asymmetry": 0.002}), ("baseline_polynomial", {"degree": 2})])
def test_baselines_pass_under_the_peaks(name: str, args: dict) -> None:
    background = 1 + 0.2 * X - 0.01 * X ** 2
    y = background + 2 * np.exp(-(X - 3) ** 2 / 0.08) + 1.2 * np.exp(-(X - 7) ** 2 / 0.05)
    out = run(name, X, y, args)
    assert np.max(np.abs(col(out, "Baseline") - background)) < 0.06
    assert col(out, "Baseline removed").max() == pytest.approx(2, abs=0.08)
    flipped = run(name, X, -y, {**args, "flip": True})
    assert col(flipped, "Baseline") == pytest.approx(-col(out, "Baseline"), abs=1e-9)


def test_peaks_are_found_with_their_width_and_area() -> None:
    y = 2 * np.exp(-(X - 3) ** 2 / (2 * 0.2 ** 2)) + 1 * np.exp(-(X - 7) ** 2 / (2 * 0.3 ** 2))
    out = run("find_peaks", X, y, {"prominence": 0.1})
    assert out["sheet"] == "new" and col(out, "Position") == pytest.approx([3, 7], abs=0.01) and col(out, "Height") == pytest.approx([2, 1], abs=1e-3)
    assert col(out, "FWHM") == pytest.approx([2.3548 * 0.2, 2.3548 * 0.3], rel=1e-3)
    assert col(out, "Area") == pytest.approx([2 * 0.2 * math.sqrt(2 * math.pi), 0.3 * math.sqrt(2 * math.pi)], rel=1e-3)
    assert len(col(run("find_peaks", X, -y, {"flip": True}), "Position")) == 2 and len(col(run("find_peaks", X, y, {"prominence": 0.6}), "Position")) == 1


def test_fourier_transform_reads_amplitude_and_frequency() -> None:
    t = np.arange(2000) * 0.001
    y = 1.5 + 3 * np.sin(2 * math.pi * 50 * t) + 0.5 * np.sin(2 * math.pi * 120 * t + 1)
    out = run("fft", t, y, {"window": "none"})
    assert fact(out, "Strongest frequency")["value"] == pytest.approx(50) and fact(out, "Its amplitude")["value"] == pytest.approx(3, rel=1e-6)
    freq, amp = col(out, "Frequency"), col(out, "Amplitude")
    assert amp[np.argmin(abs(freq - 120))] == pytest.approx(0.5, rel=1e-6) and fact(out, "Highest frequency")["value"] == pytest.approx(500)
    assert col(run("fft", t, y, {"window": "hann"}), "Amplitude")[np.argmin(abs(freq - 50))] == pytest.approx(3, rel=2e-3)
    with pytest.raises(AnalysisError, match="evenly spaced"):
        run("fft", t ** 2, y)


def test_regression_agrees_with_scipy() -> None:
    rng = np.random.default_rng(4)
    x = np.linspace(0, 5, 40)
    y = 2.5 * x - 1 + rng.normal(0, 0.3, x.size)
    from scipy import stats
    ref = stats.linregress(x, y)
    out = run("polyfit", x, y)
    assert fact(out, "Slope")["value"] == pytest.approx(ref.slope) and fact(out, "Slope")["error"] == pytest.approx(ref.stderr)
    assert fact(out, "Intercept")["error"] == pytest.approx(ref.intercept_stderr) and fact(out, "R²")["value"] == pytest.approx(ref.rvalue ** 2)
    assert fact(out, "p-value")["value"] == pytest.approx(ref.pvalue, rel=1e-6)
    cubic = run("polyfit", x, 1 + x - 2 * x ** 3, {"degree": 3})
    assert [fact(cubic, f"c{i}")["value"] for i in range(4)] == pytest.approx([1, 1, 0, -2], abs=1e-9)


def test_statistics_normalise_interpolate_histogram_combine() -> None:
    y = np.array([2.0, 4, 4, 4, 5, 5, 7, 9])
    x = np.arange(8.0)
    d = run("describe", x, y)
    assert fact(d, "Mean")["value"] == 5 and fact(d, "Standard deviation")["value"] == pytest.approx(2.13809, abs=1e-5) and fact(d, "Median")["value"] == 4.5
    assert col(run("normalise", x, y, {"mode": "range"}), "Normalised")[[0, -1]] == pytest.approx([0, 1])
    area = col(run("normalise", x, y, {"mode": "area"}), "Normalised")
    assert np.trapezoid(area, x) == pytest.approx(1)
    with pytest.raises(AnalysisError, match="zero"):
        run("normalise", x, np.zeros(8))
    fine = run("interpolate", x, x ** 2, {"method": "cubic", "points": 71})
    assert col(fine, "Interpolated") == pytest.approx(col(fine, "x") ** 2, abs=1e-9)
    h = run("histogram", x, y, {"bins": 7})
    assert col(h, "Count").sum() == 8 and col(h, "Bin centre")[0] == pytest.approx(2.5)
    other_x = np.array([0.5, 2.5, 6.5])
    diff = col(run("combine", x, y, {"operation": "subtract", "scale": 2}, other_x, np.array([1.0, 1.0, 3.0])), "Difference")
    assert np.isnan(diff[0]) and np.isnan(diff[7]) and diff[1] == pytest.approx(4 - 2) and diff[6] == pytest.approx(7 - 5.5)


@pytest.mark.parametrize("name, args, said", [
    ("nothing", {}, "no operation is called"), ("smooth_savgol", {"window": 5, "order": 7}, "below the window"), ("smooth_savgol", {"span": 3}, "no argument called span"),
    ("smooth_moving", {"window": 5001}, "wider than the curve"), ("smooth_moving", {"window": 2.5}, "a whole number"), ("normalise", {"mode": "loud"}, "one of max"),
    ("baseline_als", {"asymmetry": 2}, "between 0.0001 and 0.5"), ("combine", {}, "needs a second curve"), ("find_peaks", {"flip": "yes"}, "yes or no"),
])
def test_refusals_say_why(name: str, args: dict, said: str) -> None:
    with pytest.raises(AnalysisError, match=said):
        run(name, X, np.sin(X), args)
