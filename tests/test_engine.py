"""Expressions, the registry of functions and the description of a model."""
from __future__ import annotations

import math

import numpy as np
import pytest

from asymille import functions, models
from asymille.expressions import Expression, ExpressionError
from asymille.models import Model, ModelError

X = np.linspace(-20, 40, 60001)


def test_expressions_compute_what_they_say() -> None:
    e = Expression("a*exp(-x/tau) + c^2 - sqrt(abs(-4))/2")
    assert e.names == ("a", "x", "tau", "c")
    assert e(a=2, x=np.array([0.0, 3.0]), tau=3, c=2) == pytest.approx([2 + 4 - 1, 2 / math.e + 3])
    assert Expression("2^3^2")() == 512 and Expression("-2^2")() == -4 and Expression("pi*e")() == pytest.approx(math.pi * math.e)
    assert Expression("max(a, 2)*atan2(1, 1)")(a=1) == pytest.approx(math.pi / 2)
    assert math.isinf(Expression("9^9^9^9")())                      # floats: a tower of powers overflows, it does not fill the memory
    assert Expression("a*exp(-x/tau)").tex() == r"a\,\mathrm{e}^{\frac{-x}{\tau}}" and Expression("(a+b)*x0^2").tex() == r"\left(a + b\right)\,x_{0}^{2}"


@pytest.mark.parametrize("text, said", [
    ("", "empty"), ("2x", "not arithmetic"), ("a +* b", "not arithmetic"), ("__import__('os')", "not a known function"), ("x.real", "only numbers, names"),
    ("x[0]", "only numbers, names"), ("'a'*3", "only numbers are allowed"), ("lambda: 1", "only numbers, names"), ("sin", "is a function"), ("sin(1, 2)", "takes 1 argument"),
    ("exp(x=1)", "takes 1 argument"), ("a if b else c", "only numbers, names"), ("a < b", "only numbers, names"), ("_private + 1", "not a name"), ("f(x)", "not a known function"),
    ("[1, 2]", "only numbers, names"), ("1" + "+1" * 1000, "longer than"), ("-" * 100 + "x", "nested too deeply"),
])
def test_expressions_refuse_everything_else(text: str, said: str) -> None:
    with pytest.raises(ExpressionError, match=said):
        Expression(text)


# where a function is looked at when it is not defined, or says nothing, on the general range
RANGES = {**dict.fromkeys(("lognormal", "power_law", "arrhenius", "hill", "stretched_exp", "langmuir", "michaelis_menten", "power_offset", "logarithm", "weibull", "planck", "bose_einstein",
                           "thermal_quenching", "thermal_quenching2", "curie_weiss"), (0.05, 30)), "vft": (200, 400), "diode": (-0.5, 0.8), "varshni": (0, 300)}


def test_every_function_of_the_registry() -> None:
    """Each one evaluates, is described, starts from the data, and its derived quantities agree with its own curve."""
    assert len(functions.REGISTRY) == 56 and {f["family"] for f in functions.described()} == set(functions.FAMILIES)
    for f in functions.REGISTRY.values():
        defaults = {p.name: p.default for p in f.params}
        x = np.linspace(*RANGES[f.name], 3000) if f.name in RANGES else X
        y = f.call(x, **defaults)
        assert y.shape == x.shape and np.all(np.isfinite(y)), f.name
        assert f.tex.startswith("y") and " = " in f.tex and all(p.label for p in f.params), f.name
        assert f.kind in ("peak", "baseline", "curve", "response"), f.name
        for d in f.derived:
            assert math.isfinite(d.of(defaults)), (f.name, d.name)
        if f.kind == "peak":
            assert f.from_peak is not None, f.name
            started = f.from_peak(5.0, 3.0, 1.5)                     # a peak at 5, 3 high, 1.5 wide at half maximum
            assert set(started) <= set(f.names) and all(math.isfinite(v) for v in started.values()), f.name
            curve = f.call(np.linspace(0.05, 30, 30000), **{**defaults, **started})
            if f.name not in ("fano", "exp_gaussian", "lognormal", "doniach"):          # these only start near the peak, by design
                assert curve.max() == pytest.approx(3.0, rel=0.03), f.name
        if f.guess is not None:
            guessed = f.guess(x, y + 0.5)
            assert set(guessed) <= set(f.names) | {"x0"} and all(math.isfinite(v) for v in guessed.values()), f.name


def test_functions_that_hold_a_convolution_or_a_limit() -> None:
    """Checked against the integral they stand for, taken numerically, and against the forms they must tend to."""
    from scipy import integrate, special
    call = {name: functions.get(name).call for name in functions.REGISTRY}
    for tau, sigma in ((2.0, 0.3), (0.05, 0.3), (50.0, 0.01), (1.0, 5.0)):            # a decay from 0, convolved with a Gaussian of unit area
        for x in (-1.0, -0.2, 0.0, 0.3, 1.0, 5.0, 20.0):
            exact = integrate.quad(lambda s, x=x, tau=tau, sigma=sigma: math.exp(-s / tau) * math.exp(-(x - s) ** 2 / (2 * sigma ** 2)) / (sigma * math.sqrt(2 * math.pi)),
                                   0, max(x, 0) + 10 * sigma, points=[x] if x > 0 else None, limit=400)[0]
            assert call["decay_gauss"](np.array([x]), 0.0, 1.0, tau, 0.0, sigma)[0] == pytest.approx(exact, rel=1e-9, abs=1e-13), (tau, sigma, x)
    assert call["decay_gauss"](np.array([-1.0, 2.0]), 0.5, 3.0, 2.0, 0.0, 0.0) == pytest.approx([0.5, 0.5 + 3 / math.e])           # no width: a plain decay from x0
    two = call["decay2_gauss"](X, 0.1, 2.0, 1.0, 3.0, 5.0, 0.5, 0.2)
    assert two == pytest.approx(0.1 + call["decay_gauss"](X, 0, 2.0, 1.0, 0.5, 0.2) + call["decay_gauss"](X, 0, 3.0, 5.0, 0.5, 0.2))
    x = np.linspace(-1, 1, 41)
    for kt, sigma in ((0.025, 0.05), (0.05, 0.025), (0.05, 0.0499), (0.05, 0.0501), (0.1, 1e-4)):           # a Fermi edge through a Gaussian, on both sides of where the sum changes hands
        exact = [integrate.quad(lambda s, v=v, kt=kt, sigma=sigma: special.expit(-(v - s) / kt) * math.exp(-s ** 2 / (2 * sigma ** 2)) / (sigma * math.sqrt(2 * math.pi)),
                                -10 * sigma, 10 * sigma, limit=800)[0] for v in x]
        assert call["fermi_gaussian"](x, 1.0, 0.0, kt, sigma) == pytest.approx(exact, abs=1e-12), (kt, sigma)
    assert call["fermi_gaussian"](x, 2.0, 0.1, 1e-7, 0.1) == pytest.approx(special.erfc((x - 0.1) / (0.1 * math.sqrt(2))), abs=1e-6)       # no temperature: an error-function step
    assert call["fermi_gaussian"](x, 2.0, 0.1, 0.05, 0.0) == pytest.approx(call["fermi_dirac"](x, 2.0, 0.1, 0.05))                       # no resolution: the edge itself
    h = np.linspace(-5, 5, 101)
    assert call["brillouin"](h, 1.0, 0.5, 1.0) == pytest.approx(np.tanh(h)) and call["brillouin"](h, 2.0, 400.0, 1.0) == pytest.approx(call["langevin"](h, 2.0, 1.0), abs=3e-3)
    assert call["langevin"](np.array([1e-4, 2e-3, 1.0]), 3.0, 1.0) == pytest.approx([1e-4, 3 * (1 / math.tanh(2e-3) - 500), 3 * (1 / math.tanh(1) - 1)], rel=1e-9)
    d = 1e-5
    slope = (call["lorentzian"](X + d, 3.0, 4.0, 1.3) - call["lorentzian"](X - d, 3.0, 4.0, 1.3)) / (2 * d)
    assert call["lorentzian_derivative"](X, 3.0, 4.0, 1.3) == pytest.approx(slope, abs=1e-8)
    found = functions.get("lorentzian_derivative").guess(X, call["lorentzian_derivative"](X, 3.0, 4.0, 1.3))
    assert (found["center"], found["sigma"], found["amplitude"]) == pytest.approx((4.0, 1.3, 3.0), rel=2e-3)
    wavelength = np.linspace(0.1, 10, 990001)
    assert wavelength[np.argmax(call["planck"](wavelength, 1.0, 5000.0))] == pytest.approx(functions.get("planck").derived[0].of({"A": 1.0, "T": 5000.0}), abs=2e-5)
    t = np.linspace(5, 300, 60)
    assert call["thermal_quenching2"](t, i0=2.0, c=50.0, ea=0.01, c2=0.0, ea2=0.05) == pytest.approx(call["thermal_quenching"](t, i0=2.0, c=50.0, ea=0.01))
    assert call["weibull"](np.array([0.0, 2.0]), 4.0, 2.0, 1.7) == pytest.approx([0, 4 * (1 - 1 / math.e)]) and call["gompertz"](np.array([3.0]), 5.0, 3.0, 2.0)[0] == pytest.approx(5 / math.e)


@pytest.mark.parametrize("name", ["gaussian", "lorentzian", "voigt", "pseudo_voigt", "pearson7", "moffat", "split_lorentzian", "split_gaussian", "sinc2"])
def test_derived_width_and_height_agree_with_the_curve(name: str) -> None:
    f = functions.get(name)
    values = {"amplitude": 3.0, "center": 4.0, "sigma": 1.3, "gamma": 0.7, "fraction": 0.35, "expon": 2.2, "beta": 1.7, "sigma_r": 2.1, "width": 1.9}
    values = {k: v for k, v in values.items() if k in f.names}
    x = np.linspace(-200, 200, 4_000_001)
    y = f.call(x, **values)
    derived = {d.name: d.of(values) for d in f.derived}
    top = float(y.max())
    if "height" in derived:
        assert derived["height"] == pytest.approx(top, rel=1e-6)
    above = x[y >= top / 2]
    assert derived["fwhm"] == pytest.approx(above[-1] - above[0], rel=3e-4 if name in ("voigt", "sinc2") else 1e-4)        # Voigt: an approximation good to 0.02 %; sinc²: the grid is 1e-4 of its width
    if f.params[0].label == "area under the peak":
        assert np.trapezoid(y, x) == pytest.approx(3.0, rel=1e-2 if name in ("lorentzian", "voigt", "pseudo_voigt", "split_lorentzian") else 1e-6)        # Lorentzian wings reach beyond ±200


SPEC = {"components": [
    {"id": "p1", "fn": "gaussian", "params": {"center": {"value": 5.0}, "sigma": {"value": 1.0, "min": 0.1, "max": 3.0}}},
    {"id": "p2", "fn": "lorentzian", "params": {"amplitude": {"value": 2.0, "vary": False}, "center": {"value": 8.0, "expr": "p1_center + 3.2"}}},
    {"id": "u", "fn": "expression", "expr": "a*exp(-x/tau) + c", "params": {"a": 1.5, "tau": {"value": 2.0, "min": 0.0}}},
]}


def test_a_model_is_the_sum_of_its_components() -> None:
    model = Model(SPEC)
    assert model.names == ["p1_amplitude", "p1_center", "p1_sigma", "p2_amplitude", "p2_center", "p2_sigma", "u_a", "u_tau", "u_c"]
    params = model.parameters()
    assert params["p2_center"].value == pytest.approx(8.2) and not params["p2_center"].vary and not params["p2_amplitude"].vary
    assert params["p1_sigma"].min == 0.1 and params["p2_sigma"].min == 0 and params["u_c"].value == 1.0        # the registry's bound; a default of 1
    x = np.linspace(0, 12, 50)
    parts = model.parts(params, x)
    assert model.evaluate(params, x) == pytest.approx(parts["p1"] + parts["p2"] + parts["u"])
    assert parts["u"] == pytest.approx(1.5 * np.exp(-x / 2) + 1)
    assert [d[0] for d in model.derived(params)] == ["p1_fwhm", "p1_height", "p2_fwhm", "p2_height"]
    assert len(model.tex()) == 3 and model.tex()[2]["tex"].startswith(r"y_{\mathrm{u}} = a\,\mathrm{e}")


def test_a_model_written_on_one_line_reads_back_the_same() -> None:
    text = models.write(SPEC)
    assert text == ("p1:gaussian(amplitude~1, center~5, sigma~1, sigma>0.1, sigma<3) + p2:lorentzian(amplitude=2, sigma~1 | center = p1_center + 3.2)"
                    " + u:{a*exp(-x/tau) + c}(a~1.5, tau~2, tau>0, c~1)")
    assert models.normalised(models.parse(text)) == models.normalised(SPEC)
    by_hand = models.parse("g:gaussian(center~3, sigma>0.5) + bg:linear + e:{k*x^2}(k=0.5)")
    assert by_hand["components"][1] == {"id": "bg", "fn": "linear", "params": {}} and by_hand["components"][2]["params"]["k"] == {"value": 0.5, "vary": False}


@pytest.mark.parametrize("spec, said", [
    ({"components": [{"id": "P1", "fn": "gaussian"}]}, "needs an id"), ({"components": [{"id": "a", "fn": "gaussian"}, {"id": "a", "fn": "linear"}]}, "two components are called a"),
    ({"components": [{"id": "a", "fn": "gaussian", "params": {"width": 1}}]}, "no parameter called width: it has amplitude, center, sigma"),
    ({"components": [{"id": "a", "fn": "gaussian", "params": {"sigma": {"value": 1, "min": 2, "max": 1}}}]}, "lower bound is not below"),
    ({"components": [{"id": "a", "fn": "gaussian", "params": {"sigma": {"value": float("nan")}}}]}, "is not a number"),
    ({"components": [{"id": "a", "fn": "gaussian", "params": {"sigma": {"value": 1, "start": 2}}}]}, "a parameter is a number, or value"),
    ({"components": [{"id": "a", "fn": "gaussian", "params": {"sigma": {"value": 1, "expr": "b_center"}}}]}, "the tie of a_sigma: unknown name: b_center"),
    ({"components": [{"id": "a", "fn": "expression", "expr": "k*y"}] * 41}, "40 components at most"),
])
def test_a_model_that_is_not_one_says_why(spec: dict, said: str) -> None:
    with pytest.raises(ModelError, match=said):
        Model(spec)


@pytest.mark.parametrize("text, said", [("gaussian()", "not written as name:function"), ("a:gaussian(center)", "is not a setting"), ("a:gaussian(center~1", "not closed"),
                                        ("a:gaussian(center~1 | sigma)", "is not a tie"), ("a:nothing()", "no fit function")])
def test_a_line_that_is_not_a_model_says_why(text: str, said: str) -> None:
    with pytest.raises(ModelError, match=said):
        models.parse(text)
