"""The fitting engine: against NIST certified values, on data made with known parameters, and its refusals."""
from __future__ import annotations

import math

import numpy as np
import pytest
from nist import load

from asymille import fitting
from asymille.fitting import FitError, compare, fit, fit_global, guess

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


# ── errors on both axes ──────────────────────────────────────────────────────
# Pearson's data with York's weights: the line every method for errors on x and y is checked on (York et al., Am. J. Phys. 72, 367, 2004).
PEARSON_X = [0.0, 0.9, 1.8, 2.6, 3.3, 4.4, 5.2, 6.1, 6.5, 7.4]
PEARSON_Y = [5.9, 5.4, 4.4, 4.6, 3.5, 3.7, 2.8, 2.8, 2.4, 1.5]
PEARSON_WX = [1000, 1000, 500, 800, 200, 80, 60, 20, 1.8, 1.0]
PEARSON_WY = [1.0, 1.8, 4.0, 8.0, 20, 20, 70, 70, 100, 500]
LINE = {"components": [{"id": "b", "fn": "linear", "params": {"slope": {"value": -1}, "intercept": {"value": 5}}}]}


def test_a_line_with_errors_on_x_and_y_is_yorks() -> None:
    sx, sy = 1 / np.sqrt(PEARSON_WX), 1 / np.sqrt(PEARSON_WY)
    result = fit(PEARSON_X, PEARSON_Y, LINE, sigma=sy, sigma_x=sx, weights="instrumental", absolute_sigma=True)
    found = by_name(result)
    assert result["success"] and result["x_errors"]
    assert found["b_slope"]["value"] == pytest.approx(-0.48053341, abs=5e-9) and found["b_intercept"]["value"] == pytest.approx(5.47991022, abs=5e-9)        # York's published values
    assert result["chisqr"] == pytest.approx(11.8663531941, rel=1e-10)
    # the standard errors are ODRPACK's (scipy.odr 1.18): York's own formula gives 0.0576 and 0.2919, within 1 %
    assert found["b_slope"]["stderr"] == pytest.approx(0.05798497, rel=1e-6) and found["b_intercept"]["stderr"] == pytest.approx(0.29497058, rel=1e-6)
    scaled = by_name(fit(PEARSON_X, PEARSON_Y, LINE, sigma=sy, sigma_x=sx, weights="instrumental"))
    assert scaled["b_slope"]["stderr"] == pytest.approx(0.07062022, rel=1e-6) and scaled["b_intercept"]["stderr"] == pytest.approx(0.35924634, rel=1e-6)
    vertical = by_name(fit(PEARSON_X, PEARSON_Y, LINE, sigma=sy, weights="instrumental"))
    assert vertical["b_slope"]["value"] == pytest.approx(-0.6108, abs=1e-3)              # counting the errors of y alone gives another line
    exact = fit(PEARSON_X, PEARSON_Y, LINE, sigma=sy, sigma_x=np.zeros(10), weights="instrumental")
    assert by_name(exact)["b_slope"]["value"] == pytest.approx(vertical["b_slope"]["value"], rel=1e-9)        # an x without error counts as before


@pytest.mark.parametrize("fn, start, truth, odrpack, sd, rss, rel", [
    # what ODRPACK (scipy.odr 1.18) gives on the same points: parameters, their standard deviations, the sum of squares
    ("gaussian", {"amplitude": 1.5, "center": 0, "sigma": 0.8}, lambda x: 2 / (0.6 * math.sqrt(2 * math.pi)) * np.exp(-(x - 0.3) ** 2 / 0.72),
     {"amplitude": 2.014818233074, "center": 0.310299226672, "sigma": 0.594146663109}, {"amplitude": 0.049508078619, "center": 0.020683881991, "sigma": 0.013812826954}, 30.11824813763694, 1e-7),
    ("exp_decay", {"A": 2, "tau": 1, "y0": 0.1}, lambda x: 3 * np.exp(-x / 1.5) + 0.4,
     {"A": 3.054938643826, "tau": 1.47194783176, "y0": 0.404136357878}, {"A": 0.05260028505, "tau": 0.041273163907, "y0": 0.013951679483}, 18.64926423975261, 3e-6),
])
def test_a_curve_with_errors_on_x_and_y_agrees_with_odrpack(fn: str, start: dict, truth, odrpack: dict, sd: dict, rss: float, rel: float) -> None:
    n = 60 if fn == "gaussian" else 40
    i = np.arange(n)
    xt = np.linspace(-3, 3, n) if fn == "gaussian" else np.linspace(0.2, 6, n)
    sx, sy = (np.full(n, 0.15), np.full(n, 0.03)) if fn == "gaussian" else (0.05 + 0.03 * xt, np.full(n, 0.04))
    x, y = xt + sx * np.sin(7 * i), truth(xt) + sy * np.cos(11 * i)                # scatter without random numbers: the same points everywhere
    spec = {"components": [{"id": "m", "fn": fn, "params": {k: {"value": v} for k, v in start.items()}}]}
    result = fit(x, y, spec, sigma=sy, sigma_x=sx, weights="instrumental")
    found = by_name(result)
    assert result["success"] and not result["warnings"]
    for name, value in odrpack.items():
        assert found[f"m_{name}"]["value"] == pytest.approx(value, rel=rel), name
        assert found[f"m_{name}"]["stderr"] == pytest.approx(sd[name], rel=10 * rel), name
    assert result["chisqr"] == pytest.approx(rss, rel=1e-9)
    assert len(result["residuals"]["standardised"]) == n and sum(v ** 2 for v in result["residuals"]["standardised"]) == pytest.approx(result["nfree"], rel=1e-9)


def test_errors_on_x_need_errors_on_y() -> None:
    with pytest.raises(FitError, match="together with errors on y"):
        fit(PEARSON_X, PEARSON_Y, LINE, sigma_x=np.ones(10))
    with pytest.raises(FitError, match="as long as the data"):
        fit(PEARSON_X, PEARSON_Y, LINE, sigma=np.ones(10), sigma_x=np.ones(9), weights="instrumental")
    some = np.ones(10)
    some[3] = np.nan                                                                # a point without its error of x is left out, like one without its error of y
    assert fit(PEARSON_X, PEARSON_Y, LINE, sigma=np.ones(10), sigma_x=some, weights="instrumental")["npoints"] == 9


# ── through the response of the instrument ───────────────────────────────────
T = np.arange(1024) * 0.05
IRF = np.exp(-(T - 5) ** 2 / (2 * 0.17 ** 2)) + 0.02 * np.exp(-(T - 5.6) ** 2 / (2 * 0.3 ** 2))             # a pulse with a small tail, 0.4 wide
DECAY = {"components": [{"id": "r", "fn": "response"}, {"id": "e", "fn": "exp_decay2", "params": {"y0": {"value": 0, "vary": False}}}, {"id": "b", "fn": "constant"}]}


def seen(shift: float, a1: float, tau1: float, a2: float, tau2: float, level: float) -> np.ndarray:
    """Two decays as the instrument shows them, written here without the engine: the response moved, a plain sum for the convolution."""
    kernel = np.interp(T - shift, T, IRF / IRF.sum(), left=0, right=0)
    decay = a1 * np.exp(-T / tau1) + a2 * np.exp(-T / tau2)
    return np.array([np.sum(kernel[: j + 1] * decay[j::-1]) for j in range(len(T))]) + level


def test_a_decay_through_a_measured_response() -> None:
    y = seen(0.031, 9000, 1.2, 3000, 6.0, 12.0)
    started = guess(T, y, DECAY)
    result = fit(T, y, started, response=IRF * 1000)                               # the scale of the response does not matter: it is brought to a sum of 1
    found = by_name(result)
    assert result["success"] and result["response"] and not result["warnings"]
    decays = sorted((found[f"e_tau{k}"]["value"], found[f"e_A{k}"]["value"]) for k in (1, 2))            # the two decays may come in either order
    assert decays == [pytest.approx((1.2, 9000), rel=1e-6), pytest.approx((6.0, 3000), rel=1e-6)]
    assert found["r_shift"]["value"] == pytest.approx(0.031, rel=1e-6) and found["b_c"]["value"] == pytest.approx(12.0, rel=1e-6)
    assert result["curve"]["x"] == pytest.approx(T) and set(result["curve"]["components"]) == {"e", "b"}       # the curve is where the instrument measured; the response is not a curve
    assert result["curve"]["components"]["b"] == pytest.approx(np.full(1024, 12.0)) and result["curve"]["y"] == pytest.approx(y, rel=1e-6)
    late = fit(T, y, started, response=IRF, limits=[8, 40])                        # a range after the pulse: the response before it still counts
    assert max(by_name(late)[f"e_tau{k}"]["value"] for k in (1, 2)) == pytest.approx(6.0, rel=1e-6) and late["npoints"] == 641 and late["curve"]["x"][0] == pytest.approx(8.0)
    plain = fit(T[110:], y[110:], {"components": DECAY["components"][1:]})
    assert abs(min(by_name(plain)[f"e_tau{k}"]["value"] for k in (1, 2)) - 1.2) > 0.01            # without the response the short decay is not the true one
    before = fitting.evaluate(started, T, IRF)
    assert len(before["y"]) == 1024 and set(before["components"]) == {"e", "b"}


def test_counting_noise_through_a_response() -> None:
    rng = np.random.default_rng(1)
    y = rng.poisson(seen(0.0, 9000, 1.2, 3000, 6.0, 12.0)).astype(float)
    result = fit(T, y, guess(T, y, DECAY), response=IRF, weights="statistical")
    found = by_name(result)
    short, long = sorted((1, 2), key=lambda k: found[f"e_tau{k}"]["value"])
    for name, value in {f"e_tau{short}": 1.2, f"e_tau{long}": 6.0, f"e_A{short}": 9000, f"e_A{long}": 3000}.items():
        assert abs(found[name]["value"] - value) < 4 * found[name]["stderr"], name
    assert 0.8 < result["redchi"] < 1.2 and found[f"e_tau{short}"]["stderr"] < 0.02


def test_one_response_for_each_dataset_of_a_global_fit() -> None:
    spec = {"components": [{"id": "r", "fn": "response", "params": {"shift": {"value": 0, "vary": False}}}, {"id": "e", "fn": "exp_decay", "params": {"y0": {"value": 0, "vary": False}, "A": {"value": 4000}}},
                           {"id": "b", "fn": "constant"}]}
    wide = np.exp(-(T - 5) ** 2 / (2 * 0.4 ** 2))
    one = seen(0.0, 5000, 2.0, 0, 1, 5)
    kernel = wide / wide.sum()
    two = np.array([np.sum(kernel[: j + 1] * (9000 * np.exp(-T / 2.0))[j::-1]) for j in range(len(T))]) + 8
    result = fit_global([{"x": T, "y": one, "response": IRF}, {"x": T, "y": two, "response": wide}], spec, ["e_tau"])
    assert [by_name(d)["e_A"]["value"] for d in result["datasets"]] == pytest.approx([5000, 9000], rel=1e-6) and by_name(result["datasets"][1])["e_tau"]["value"] == pytest.approx(2.0, rel=1e-6)


@pytest.mark.parametrize("more, said", [
    ({}, "choose the column that holds it"), ({"response": IRF[:-1]}, "as long as the data"), ({"response": IRF * 0}, "its sum is not positive"),
    ({"response": IRF, "x": np.where(np.arange(1024) == 500, T + 0.02, T)}, "x must increase by even steps"),
    ({"response": IRF, "sigma": np.ones(1024), "sigma_x": np.ones(1024), "weights": "instrumental"}, "cannot be counted with a measured response"),
    ({"response": IRF, "spec": {"components": [{"id": "r", "fn": "response"}, {"id": "b", "fn": "linear"}]}}, "needs something to act on"),
    ({"response": IRF, "spec": {"components": [{"id": "r", "fn": "response"}, {"id": "q", "fn": "response"}, {"id": "e", "fn": "exp_decay"}]}}, "one instrument response at most"),
])
def test_a_response_that_cannot_be_used_says_why(more: dict, said: str) -> None:
    more = dict(more)
    with pytest.raises(FitError, match=said):
        fit(more.pop("x", T), seen(0, 100, 2, 0, 1, 0), more.pop("spec", DECAY), **more)


# ── which model ──────────────────────────────────────────────────────────────
def test_two_models_of_the_same_points_are_compared() -> None:
    x = np.linspace(0, 10, 200)
    y = 3 * np.exp(-x / 0.8) + 1.5 * np.exp(-x / 4) + 0.2 + 0.02 * np.cos(37 * np.arange(200))
    one = fit(x, y, {"components": [{"id": "e", "fn": "exp_decay", "params": {"A": {"value": 4}, "tau": {"value": 2}}}]})
    two = fit(x, y, {"components": [{"id": "e", "fn": "exp_decay2", "params": {"A1": {"value": 3}, "tau1": {"value": 1}, "A2": {"value": 1}, "tau2": {"value": 5}}}]})
    said = compare([{"name": "one decay", **{k: one[k] for k in ("ndata", "nvarys", "chisqr")}}, {"name": "two decays", **{k: two[k] for k in ("ndata", "nvarys", "chisqr")}}])
    first, second = said["fits"]
    assert said["best"] == "two decays" and said["by"] == "aicc" and second["delta"] == 0 and first["weight"] + second["weight"] == pytest.approx(1)
    assert first["aic"] == pytest.approx(one["aic"]) and second["bic"] == pytest.approx(two["bic"])                 # the same AIC and BIC as each fit shows
    assert second["aicc"] == pytest.approx(two["aic"] + 2 * 5 * 6 / (200 - 5 - 1))
    test = said["tests"][0]
    expected = ((one["chisqr"] - two["chisqr"]) / 2) / (two["chisqr"] / 195)
    assert (test["simpler"], test["fuller"], test["df"]) == ("one decay", "two decays", [2, 195]) and test["f"] == pytest.approx(expected) and test["p"] < 1e-50
    assert "holds only if “one decay” is a special case" in test["said"] and "is the one the data support" in said["said"]
    same = compare([{"name": "a", "ndata": 50, "nvarys": 3, "chisqr": 10.0}, {"name": "b", "ndata": 50, "nvarys": 3, "chisqr": 10.2}, {"name": "c", "ndata": 50, "nvarys": 4, "chisqr": 10.4}])
    assert "do not tell" in same["said"] and len(same["tests"]) == 2 and same["tests"][0]["f"] is None            # as many parameters: no F test; more parameters and no better: nothing to test
    far = compare([{"name": "a", "ndata": 600, "nvarys": 4, "chisqr": 34875.3}, {"name": "b", "ndata": 600, "nvarys": 6, "chisqr": 674.1}])            # so far apart that the ratio of likelihoods overflows
    assert far["best"] == "b" and far["fits"][0]["weight"] == 0 and "no support left" in far["said"] and "p < 1e-300" in far["tests"][0]["said"] and far["tests"][0]["p"] == 0
    with pytest.raises(FitError, match="only fits of the same points"):
        compare([{"name": "a", "ndata": 50, "nvarys": 3, "chisqr": 10.0}, {"name": "b", "ndata": 49, "nvarys": 3, "chisqr": 10.5}])
    with pytest.raises(FitError, match="between 2 and 12"):
        compare([{"name": "a", "ndata": 50, "nvarys": 3, "chisqr": 10.0}])
