"""The fitting engine: against NIST certified values, on data made with known parameters, and its refusals."""
from __future__ import annotations

import math

import numpy as np
import pytest
from nist import load

from asymille import fitting
from asymille.fitting import FitError, fit, fit_global, guess

# each NIST problem as an Asymille model: the expression, and which starting values of NIST are used
NIST = {
    "Misra1a": ("b1*(1-exp(-b2*x))", 0),
    "Thurber": ("(b1 + b2*x + b3*x^2 + b4*x^3) / (1 + b5*x + b6*x^2 + b7*x^3)", 1),
    "Lanczos3": ("b1*exp(-b2*x) + b3*exp(-b4*x) + b5*exp(-b6*x)", 1),
    "Gauss2": ("b1*exp(-b2*x) + b3*exp(-(x-b4)^2/b5^2) + b6*exp(-(x-b7)^2/b8^2)", 1),
}


def by_name(result: dict) -> dict:
    return {p["name"]: p for p in result["params"]}


@pytest.mark.parametrize("name", list(NIST))
def test_nist_certified_values(name: str) -> None:
    """Parameters, their standard deviations and the residual sum of squares agree with what NIST certifies."""
    data, (expr, start) = load(name), NIST[name]
    spec = {"components": [{"id": "m", "fn": "expression", "expr": expr, "params": {k: {"value": v[start]} for k, v in data["starts"].items()}}]}
    result = fit(data["x"], data["y"], spec)
    assert result["success"], result["message"]
    found = by_name(result)
    for key, (value, sd) in data["certified"].items():
        assert found[f"m_{key}"]["value"] == pytest.approx(value, rel=1e-6), key
        assert found[f"m_{key}"]["stderr"] == pytest.approx(sd, rel=1e-4), key
    assert result["chisqr"] == pytest.approx(data["rss"], rel=1e-7)
    assert result["nfree"] == len(data["x"]) - len(data["certified"])


def test_gauss2_with_registry_functions() -> None:
    """The same NIST problem built from the registry (an exponential and two Gaussians) reaches the certified sum of squares."""
    data = load("Gauss2")
    spec = {"components": [{"id": "bg", "fn": "exp_decay", "params": {"y0": {"value": 0, "vary": False}, "A": 96, "tau": 100}},
                           {"id": "p1", "fn": "gaussian", "params": {"amplitude": 2500, "center": 105, "sigma": 14}},
                           {"id": "p2", "fn": "gaussian", "params": {"amplitude": 2200, "center": 150, "sigma": 14}}]}
    result = fit(data["x"], data["y"], spec)
    cert = data["certified"]
    found = by_name(result)
    assert result["chisqr"] == pytest.approx(data["rss"], rel=1e-7)
    assert found["p1_center"]["value"] == pytest.approx(cert["b4"][0], rel=1e-6)
    assert found["p1_center"]["stderr"] == pytest.approx(cert["b4"][1], rel=1e-4)
    assert found["bg_tau"]["value"] == pytest.approx(1 / cert["b2"][0], rel=1e-6)
    # NIST writes exp(-(x-b4)²/b5²): b5 = σ√2, and the height b3 is derived here from the area
    assert found["p1_sigma"]["value"] * math.sqrt(2) == pytest.approx(cert["b5"][0], rel=1e-6)
    derived = {d["name"]: d for d in result["derived"]}
    assert derived["p1_height"]["value"] == pytest.approx(cert["b3"][0], rel=1e-6)
    assert derived["p1_height"]["stderr"] == pytest.approx(cert["b3"][1], rel=1e-3)        # propagated through the covariance
    assert derived["p1_fwhm"]["value"] == pytest.approx(2 * math.sqrt(math.log(2)) * cert["b5"][0], rel=1e-6)


def peaks(seed: int = 3, noise: float = 0.05):
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 20, 400)
    y = 4 * np.exp(-(x - 7) ** 2 / (2 * 0.8 ** 2)) + 2.5 / (1 + ((x - 12.5) / 0.6) ** 2) + 0.3 + 0.02 * x
    return x, y + rng.normal(0, noise, x.size), noise


TWO = {"components": [{"id": "g", "fn": "gaussian", "params": {}}, {"id": "l", "fn": "lorentzian", "params": {}}, {"id": "bg", "fn": "linear", "params": {}}]}


def test_guess_then_fit_recovers_known_peaks() -> None:
    x, y, noise = peaks()
    started = guess(x, y, TWO)
    centers = {c["id"]: c["params"].get("center", {}).get("value") for c in started["components"]}
    assert centers["g"] == pytest.approx(7, abs=0.3) and centers["l"] == pytest.approx(12.5, abs=0.3)
    result = fit(x, y, started)
    found = by_name(result)
    for name, truth in {"g_center": 7, "g_sigma": 0.8, "l_center": 12.5, "l_sigma": 0.6, "bg_slope": 0.02, "bg_intercept": 0.3}.items():
        assert abs(found[name]["value"] - truth) < 4 * found[name]["stderr"], name
    derived = {d["name"]: d for d in result["derived"]}
    assert derived["g_height"]["value"] == pytest.approx(4, abs=4 * derived["g_height"]["stderr"])
    assert derived["l_fwhm"]["value"] == pytest.approx(1.2, abs=4 * derived["l_fwhm"]["stderr"])
    assert math.sqrt(result["redchi"]) == pytest.approx(noise, rel=0.15)                      # unweighted: reduced χ² estimates the noise
    assert result["rsquared"] > 0.99 and not result["warnings"]
    assert len(result["curve"]["x"]) == 800 and set(result["curve"]["components"]) == {"g", "l", "bg"}


def test_instrumental_weights_and_absolute_sigma() -> None:
    x, y, noise = peaks(seed=5)
    sigma = np.full_like(x, noise)
    scaled = fit(x, y, guess(x, y, TWO), sigma=sigma, weights="instrumental")
    absolute = fit(x, y, guess(x, y, TWO), sigma=sigma, weights="instrumental", absolute_sigma=True)
    assert absolute["redchi"] == pytest.approx(1, abs=0.2) and 0.001 < absolute["p_value"] < 0.999
    ratio = by_name(scaled)["g_center"]["stderr"] / by_name(absolute)["g_center"]["stderr"]
    assert ratio == pytest.approx(math.sqrt(scaled["redchi"]), rel=1e-6)                      # the only difference is the rescaling by χ²
    assert absolute["curve"]["prediction"] is None and absolute["curve"]["band"] is not None


def test_confidence_band_covers_the_true_curve() -> None:
    covered = []
    for seed in range(40):
        rng = np.random.default_rng(seed)
        x = np.linspace(0, 10, 60)
        y = 2 + 5 * np.exp(-x / 2.5) + rng.normal(0, 0.2, x.size)
        r = fit(x, y, {"components": [{"id": "d", "fn": "exp_decay", "params": {"y0": 1, "A": 3, "tau": 1}}]}, points=50)
        gx = np.array(r["curve"]["x"])
        truth = 2 + 5 * np.exp(-gx / 2.5)
        covered.append(np.mean((np.array(r["curve"]["band"]["lower"]) <= truth) & (truth <= np.array(r["curve"]["band"]["upper"]))))
    assert 0.88 < np.mean(covered) < 0.99            # a 95 % band, pointwise


def test_ties_fixed_values_and_bounds() -> None:
    x, y, _ = peaks()
    spec = guess(x, y, TWO)
    spec["components"][1]["params"]["center"] = {"value": 12, "expr": "g_center + 5.5"}
    spec["components"][2]["params"]["slope"] = {"value": 0.02, "vary": False}
    result = fit(x, y, spec)
    found = by_name(result)
    assert found["l_center"]["value"] == pytest.approx(found["g_center"]["value"] + 5.5)
    assert found["l_center"]["stderr"] == pytest.approx(found["g_center"]["stderr"], rel=1e-6) and not found["l_center"]["vary"]
    assert found["bg_slope"]["value"] == 0.02 and found["bg_slope"]["stderr"] is None
    assert result["nvarys"] == 6


def test_global_fit_shares_parameters() -> None:
    rng = np.random.default_rng(11)
    x = np.linspace(0, 12, 120)
    sets = [{"x": x, "y": a * np.exp(-x / 3.0) + 0.5 + rng.normal(0, 0.03, x.size)} for a in (1.0, 2.5, 4.0)]
    spec = {"components": [{"id": "d", "fn": "exp_decay", "params": {"y0": 0, "A": 1, "tau": 1}}]}
    result = fit_global(sets, spec, ["d_tau", "d_y0"])
    taus = [by_name(d)["d_tau"] for d in result["datasets"]]
    assert len({t["value"] for t in taus}) == 1 and taus[0]["value"] == pytest.approx(3.0, abs=4 * taus[0]["stderr"])
    assert taus[1]["shared"] and not taus[0]["shared"]
    assert [round(by_name(d)["d_A"]["value"], 1) for d in result["datasets"]] == [1.0, 2.5, 4.0]
    assert result["nvarys"] == 5 and result["ndata"] == 360
    alone = fit(sets[0]["x"], sets[0]["y"], spec)
    assert taus[0]["stderr"] < by_name(alone)["d_tau"]["stderr"]                               # three datasets say more than one


def test_other_methods_reach_the_same_minimum() -> None:
    x, y, _ = peaks()
    reference = fit(x, y, guess(x, y, TWO))
    for method in ("least_squares", "nelder"):
        other = fit(x, y, guess(x, y, TWO), method=method)
        assert other["chisqr"] == pytest.approx(reference["chisqr"], rel=1e-5), method
        assert by_name(other)["g_center"]["stderr"] == pytest.approx(by_name(reference)["g_center"]["stderr"], rel=1e-2), method
    bounded = guess(x, y, TWO)
    for c in bounded["components"]:
        for p in c["params"].values():
            p["min"], p["max"] = (0.001, 20) if p["value"] > 0 else (-1, 1)                   # wide: the search starts from anywhere in there
    assert fit(x, y, bounded, method="differential_evolution")["chisqr"] == pytest.approx(reference["chisqr"], rel=1e-4)


def test_robust_loss_resists_outliers() -> None:
    rng = np.random.default_rng(2)
    x = np.linspace(0, 10, 80)
    y = 1.5 * x + 2 + rng.normal(0, 0.1, x.size)
    y[::9] += 15
    line = {"components": [{"id": "l", "fn": "linear", "params": {}}]}
    plain, robust = fit(x, y, line), fit(x, y, line, method="least_squares", loss="soft_l1")
    assert abs(by_name(robust)["l_intercept"]["value"] - 2) < 0.2 < abs(by_name(plain)["l_intercept"]["value"] - 2)


def test_range_and_unusable_points() -> None:
    x, y, _ = peaks()
    y2 = y.copy()
    y2[5] = np.nan
    result = fit(x, y2, {"components": [{"id": "g", "fn": "gaussian", "params": {"center": 7, "sigma": 1, "amplitude": 8}}, {"id": "c", "fn": "constant", "params": {}}]},
                 limits=[4, 10])
    assert result["given"] == 400 and result["npoints"] == np.count_nonzero((x >= 4) & (x <= 10)) and 4 <= result["range"][0] and result["range"][1] <= 10
    assert by_name(result)["g_center"]["value"] == pytest.approx(7, abs=0.05)


def test_profile_intervals() -> None:
    x, y, _ = peaks()
    result = fit(x, y, guess(x, y, TWO), intervals=True, level=0.6827)
    row = by_name(result)["g_center"]
    low, high = row["interval"]
    assert low < row["value"] < high
    assert (high - low) / 2 == pytest.approx(row["stderr"], rel=0.15)                         # a clean valley: the profile agrees with the covariance


def test_warnings_tell_what_not_to_trust() -> None:
    x = np.linspace(0, 5, 50)
    y = 3 * np.exp(-x / 1.2)
    twins = {"components": [{"id": "a", "fn": "expression", "expr": "p*q*exp(-x/t)", "params": {"p": 1, "q": 1, "t": 1}}]}
    result = fit(x, y + np.random.default_rng(0).normal(0, 0.01, x.size), twins)
    assert any("correlated" in w or "not determined" in w or "could not be estimated" in w for w in result["warnings"])
    stuck = fit(x, y, {"components": [{"id": "d", "fn": "exp_decay", "params": {"y0": {"value": 0, "vary": False}, "A": 1, "tau": {"value": 3, "min": 2}}}]})
    assert any("ended on its bound" in w for w in stuck["warnings"])


@pytest.mark.parametrize("call, said", [
    (lambda x, y: fit(x, y, {"components": []}), "at least one component"),
    (lambda x, y: fit(x, y, {"components": [{"id": "g", "fn": "nothing"}]}), "no fit function"),
    (lambda x, y: fit(x[:3], y[:3], TWO), "parameters vary and only 3 points"),
    (lambda x, y: fit(x, y, TWO, limits=[100, 200]), "fewer than two usable points in the fit range"),
    (lambda x, y: fit(x, y, TWO, weights="instrumental"), "need an error column"),
    (lambda x, y: fit(x, y, TWO, method="differential_evolution"), "lower and an upper bound"),
    (lambda x, y: fit(x, y, {"components": [{"id": "c", "fn": "constant", "params": {"c": {"value": 1, "vary": False}}}]}), "nothing to fit"),
    (lambda x, y: fit(x, y, {"components": [{"id": "u", "fn": "expression", "expr": "__import__('os').system('id')"}]}), "not a known function"),
    (lambda x, y: fit(x, y, {"components": [{"id": "u", "fn": "expression", "expr": "a.real*x"}]}), "only numbers, names"),
    (lambda x, y: fit(x, y, {"components": [{"id": "g", "fn": "gaussian", "params": {"center": {"value": 1, "expr": "g_center*2"}}}]}), "tied to itself"),
    (lambda x, y: fit(x, y, {"components": [{"id": "g", "fn": "gaussian", "params": {"center": {"value": 1, "expr": "open('x')"}}}]}), "the tie of g_center"),
])
def test_refusals_say_why(call, said: str) -> None:
    x, y, _ = peaks()
    with pytest.raises(FitError, match=said):
        call(x, y)


def test_a_fit_that_takes_too_long_is_stopped() -> None:
    x, y, _ = peaks()
    result = fit(x, y, guess(x, y, TWO), method="nelder", timeout=0.0)
    assert not result["success"] and "stopped after" in result["message"] and result["warnings"]
    assert fitting.METHODS and fitting.WEIGHTS
