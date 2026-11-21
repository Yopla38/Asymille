# Asymille

Curve fitting, data analysis and figures for publication, in a browser. What a researcher does with a program like Origin between a measurement and a paper: bring the data in, look at them, fit a model, read what the fit is worth, and take out a figure a journal accepts.

Everything is written in English, as Ondelette is. The previous application (Django, allauth, Bootstrap, Plotly) is on `main`; this branch replaces it. Why, and what was wrong with it, is at the end.

```
page/ (plain scripts) ──► asymille/web (FastAPI routes) ──► asymille/ (the engine)
sheets, figures, the fit     projects of each user          numpy · scipy · lmfit · matplotlib
panel, undo, SVG and PNG     behind the host's accounts     fits, operations, PDF/EPS/TIFF
```

## Run it

```bash
uv sync
uv run python serve.py            # http://localhost:8780: one person, no accounts, a SQLite file in data/
```

`serve.py` is the smallest host: one local user, for a laptop. It listens on 127.0.0.1 only. To serve several people, Asymille is plugged into a server that has accounts: see "Plugged into Ondelette".

Check it:

```bash
uv run pytest                     # 124 tests: the engine, the API, the figures
node tools/check_page.js          # 29 lines: the parts of the page that hold logic, run in Node
uv run mypy && uv run ruff check asymille tests tools serve.py
```

## What it does

**Sheets.** Columns of numbers with a short name (`A`, `B`: what formulas use), a title and a unit (what an axis writes), and a role (X, Y, error on Y, error on X, labels). Type in a cell, select with the mouse or the arrows, copy and paste as tab-separated text in both directions with a spreadsheet. A column can be computed from others (`A*1000`, `sqrt(B)`, `i - 1`). Only the rows in sight are drawn, so a hundred thousand rows scroll as ten do. Sorting moves whole rows.

**Import.** Text files with columns (`.txt`, `.dat`, `.csv`…) and Tektronix RSA `.Specan` spectra, read in the browser: nothing is uploaded. The separator, the decimal mark (3.14 or 3,14), the lines of heading and the names of the columns are detected, shown with the first rows, and can be corrected before anything is kept. `Energy (eV)` in a heading becomes a title and a unit. A file dropped anywhere on the page opens the dialog.

**Graphs.** A figure has a size in millimetres and type in points, and is shown as it will be printed. Symbols, lines, steps, bars, filled areas, error bars in x and y, a second y axis, logarithmic axes, several panels with a shared x axis, panel letters, a legend that can be dragged, texts, arrows, lines and highlighted ranges. Axis titles and labels take `E_{F}`, `cm^{-1}`, `\alpha`. Drag a rectangle to zoom, the wheel zooms about the pointer, double-click shows everything again. A long curve is thinned to what a page can show (50 000 points are drawn with about 5 700).

**Journals.** 28 presets set the width, the font, the type sizes and the line widths to what a journal asks (Nature, Science, ACS, APS, AIP, Elsevier, RSC, Springer, PNAS, IEEE; a slide; a thesis page). The style of a graph can be copied to another.

**Fits.** A model is a sum of components taken from a registry of 35 functions (peaks: Gaussian, Lorentzian, Voigt, pseudo-Voigt, Pearson VII, Moffat, split Lorentzian, skewed and exponentially modified Gaussian, log-normal, Fano, Doniach–Šunjić; baselines and polynomials; decays, growth, stretched exponential, power law; sigmoids, Hill, dose–response; sines; Arrhenius, Langmuir, Michaelis–Menten, Fermi–Dirac) or written as an expression (`a*exp(-x/tau) + c`). Each parameter has a starting value, can be held, bounded, or tied to others (`p2_center = p1_center + 3.2`). Starting values are read from the data (the baseline, then the most prominent peaks). Weights: none, 1/σ² from an error column, counting statistics, constant relative error. A range of x can be dragged on the graph. Several columns can be fitted one after the other, or together with shared parameters. Methods: Levenberg–Marquardt, trust region (with a robust loss against outliers), Nelder–Mead, Powell, differential evolution.

**What a fit is worth.** Every parameter with its standard error, and on request the interval found by profiling χ²; quantities derived from the parameters (width at half maximum, height, half-life…) with their uncertainty propagated through the covariance matrix; χ², reduced χ², R², AIC, BIC, and with true error bars the probability of the χ² found; correlations; the confidence band of the curve; a panel of residuals. And warnings in words when a number should not be trusted: a fit that did not converge, a parameter on its bound, two parameters the data cannot tell apart, error bars that are too small.

**For the paper.** The table of results as tab-separated text or LaTeX, a sentence for the methods ("The data were fitted with the sum of a Gaussian, a Lorentzian and a line by non-linear least squares…"), the equations of the model, and under "What was done" one line per operation with the values used.

**Operations.** 18 of them, each writing its result in new columns and saying what it did: Savitzky–Golay, moving average, median, Gaussian and Fourier filters; derivative, integral (area, centroid); baselines (asymmetric least squares, iterative polynomial, line between the ends); peak finding (position, height, prominence, width, area); normalisation, interpolation; Fourier transform; descriptive statistics, linear and polynomial regression, histogram; combining two curves.

**Export.** SVG and PNG are made by the page; PDF, EPS and TIFF by the server, from the same figure. The file has the size asked, to the hundredth of a millimetre, with its font embedded (TrueType, type 42). When the server does not hold the font asked for, the dialog says which one the file holds.

**Projects.** Sheets, graphs and fits are one project, saved a moment after each change, with undo. Two tabs cannot overwrite each other silently. A project can be saved to a file and opened again.

## How it is made

### The engine: `asymille/`

Plain Python over numpy, scipy, lmfit and matplotlib; no web framework, no database. It can be used from a script or a notebook.

| | |
|---|---|
| `expressions.py` | Arithmetic written by a person. Read by Python's parser and then walked: numbers, names, `+ - * / ^`, parentheses and 27 functions, nothing else. No `eval`. |
| `functions.py` | The registry of fit functions: label, family, equation, what each parameter means, starting values from the data, derived quantities. The line shapes are lmfit's. |
| `models.py` | A model as data (components and parameters), and its notation on one line: `p1:gaussian(center~5, sigma>0) + bg:linear()`. |
| `fitting.py` | `fit`, `fit_global`, `guess`, `evaluate`. Minimising is lmfit's; statistics, propagation, bands and warnings are here. |
| `analysis.py` | The registry of operations. |
| `journals.py` | The presets. |
| `figures.py` | Draws a figure into PDF, EPS, TIFF or PNG with matplotlib. |

The page draws its lists from the two registries (`GET …/catalogue`): a function or an operation added in Python appears in the page with its form, without a line of JavaScript.

### One figure, two pens

`page/js/plot.js` lays a figure out: where the axes are, which ticks, where each label sits. Its result is a list of things to draw (lines, shapes, symbols, runs of text) in points on a page of a given size. The page writes that list as SVG; the server draws the same list with matplotlib, used as a pen. Neither decides anything about the figure, so the PDF holds what was on screen. Text is measured with the widths of Helvetica (the metrics of Arial and Liberation Sans), so that margins do not depend on what a browser has installed.

### The page: `page/`

Plain scripts loaded in order, no build step, attached to `window.ASY`. The charter is Ondelette's: the same variables, type and parts.

| | |
|---|---|
| `expr.js`, `importer.js`, `plot.js`, `model.js` | Logic without DOM: formulas, reading files, laying out a figure, the project. Run in Node by `tools/check_page.js`. |
| `store.js` | Keeping the project saved (after Ondelette's `store.js`). |
| `grid.js`, `figview.js` | The sheet and the figure on screen. |
| `inspect.js`, `fitpanel.js`, `dialogs.js`, `app.js` | The panels, the fit, import and export, and the wiring. |
| `shared/` | `api.js` is a copy of Ondelette's. `account.js` is a stand-in for the standalone server: plugged into Ondelette, the page loads Ondelette's own. |

### The API: `asymille/web/`

FastAPI routes under `…/asymille`, listed at the top of `api.py`. A project is a document the page writes (`model.js`) and `schemas.py` describes; a field that is not described is refused. Nothing the page sends is executed: a model is names of the registry and numbers, an expression is walked, an operation is called by its name.

## Plugged into Ondelette

Asymille has no accounts of its own. It asks the server it is plugged into for five things (`asymille/web/host.py`): its declarative base, the column an owner is, a database session, who is signed in, and how it raises an error.

```python
from asymille.web import Host, build
router = build(Host(base=Base, users="users.id", moment=UTCDateTime, db=get_db, user_id=..., error=...))
api.include_router(router)        # behind the host's own guards
```

`build` defines one table, `asymille_projects`, on the host's base: each row carries `owner_id` with `ondelete="CASCADE"`, is looked up with its owner in the query itself (somebody else's answers 404), and is created by the host's migrations.

The branch `claude/asymille-integration-ui-bigdft-osm12g` of **Bigdft_ui** holds that integration, done and tested: `backend/app/asymille.py` (the host), a migration, the page at `/asymille/`, a link in the account menu of the two workshops, `backend/tests/test_asymille.py`, and `backend/update_from_asymille.sh /path/to/Asymille [--apply]`, which copies this repository's `asymille/`, `page/index.html`, `page/js/` and the example there, unchanged. Work on Asymille here; run that script to take it there.

## What was measured, and what was not

Measured, in this repository:

- **Fits against NIST.** Four problems of the NIST StRD nonlinear regression collection (Misra1a, Thurber, Lanczos3, Gauss2, of lower, higher and average difficulty; the files are in `tests/data/` as NIST publishes them) are fitted from NIST's starting values: parameters agree with the certified values to 10⁻⁶, their standard deviations to 10⁻⁴, the residual sum of squares to 10⁻⁷. Reaching that took a last descent with a Jacobian by central differences: without it, Levenberg–Marquardt alone stopped at 10⁻⁵ on Thurber.
- **Derived quantities.** The width and height each peak function reports are compared with its own curve on a fine grid; the propagated uncertainty of a height is compared with NIST's certified one (Gauss2).
- **The confidence band.** On 40 simulated decays, a 95 % band covers the true curve at 93.4 % of its points on average (it is a pointwise band).
- **Operations.** Each on a curve whose answer is known: derivative and integral of sin, a Gaussian's area above its baseline, peaks of known width, a sine's amplitude by Fourier transform, regression against `scipy.stats.linregress`.
- **Figures.** A PDF has the size asked (to 0.01 pt), holds its font as TrueType, and is the same file when made twice. A figure laid out by the page is drawn by the server in three formats. The two were compared by eye on two figures: axes, ticks, labels and legend sit at the same places.
- **The two parsers.** The page's formula parser gives the same value as the server's on 28 expressions, and both refuse the same 20 texts that are not arithmetic.
- **The page, in a browser.** Driven with Playwright through the standalone server and through Ondelette's: import of the `.Specan` example, typing and pasting, a formula, plotting, fitting the example (centres found at 7.995 ± 0.006 and 14.494 ± 0.009 for 8 and 14.5), regression, zoom, undo, export to PDF, the list of projects, signing up. No error in the console.

Not measured, or not done:

- **The journal presets were written from memory** of the guides for authors, not re-read from the publishers' sites. The page says so beside the preset. Check the width against the journal's current guide before submitting.
- **Fonts.** The server here has Liberation Sans, not Arial: the PDF holds Liberation Sans (the same metrics), and says so. Install Arial on the server for a file that holds Arial.
- **Page and server draw the same list, with their own text engines.** Positions are the same; the exact shape of a glyph, and the width of a text that is not anchored at its start, depend on the font each one has.
- **Speed.** No timing was measured beyond the tests. A fit is stopped after 30 s; it runs in the request, four at a time for all users.
- **Size.** A project travels whole at each save, data included. The host's limit on a request (4 MB in Ondelette) bounds it: about 200 000 numbers. The page says so when a save is refused.
- **No test drives the page's panels automatically**: `check_page.js` covers the logic without DOM; the browser sessions above were run by hand with a script, not kept as a suite.
- Not there: 3D and contour plots, date axes, Excel and binary instrument formats, a peak-by-peak "click to add" on the graph, reports as PDF, scripting by the user.

## Coming from the Django application

The stack was changed for the goal, not because Django is a lesser framework: Asymille is meant to live inside Ondelette (`Bigdft_ui`), which already has accounts, sessions and a database, on FastAPI and SQLAlchemy. Two frameworks do not share sign-in simply; one process, one database and one sign-in do. The engine is independent of that choice.

What the previous code did that this one must never do:

- **It ran what a user typed.** A custom fit expression went through `sympy.parse_expr`, which evaluates Python. `asymille/expressions.py` walks a syntax tree instead, and a test sends `__import__('os')` through the API.
- **It showed a fit of random numbers when the real one failed**, as if it were a result. A fit that cannot be made now says why.
- **Any signed-in user could list and change every account** (`UserViewSet`).
- **Secrets were in the repository**: Django's `SECRET_KEY` and the PostgreSQL password, in `my_saas_app/settings.py`, with `DEBUG = True`. They are still in the history of `main`: **change that password**.
- A whole virtualenv (254 MB), `__pycache__` and `.idea` were committed; a column expression was run with `Function(...)`; `ax` was read as `a*x`, so `exp(x)` became `e*x*p(x)`; a curve was only drawn at the data points.

`legacy/corentin_dap_decay.py` is kept untouched: a donor–acceptor pair recombination model with two integrals. It was not turned into a fit function, because the two integrals do not agree on the surface element (`r dr` in the first, `dr` in the second), and which one is meant is for its author to say.
