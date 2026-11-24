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
uv run pytest                     # 149 tests: the engine, the API, the figures
node tools/check_page.js          # 76 lines: the parts of the page that hold logic, run in Node
uv run mypy && uv run ruff check asymille tests tools serve.py
```

## What it does

**Sheets.** Columns of numbers with a short name (`A`, `B`: what formulas use), a title and a unit (what an axis writes), and a role (X, Y, error on Y, error on X, labels). Type in a cell, select with the mouse or the arrows, copy and paste as tab-separated text in both directions with a spreadsheet. A column can be computed from others, as Origin's "set column values" does: row by row (`A*1000`, `sqrt(B)`, `i - 1`), from a whole column (`B/max(B)`, `B - mean(B)`; also `sum`, `sd`, `median`, `min`, `count`, and of a calculation: `max(B - A)`), from another row (`B - B[i-1]`, `B/B[1]`, `B[n]`), and with conditions (`if(A > 5 and B < 2, B, 0)`; `<`, `>`, `<=`, `>=`, `==`, `!=`, `and`, `or`, `not`). It is computed again when what it reads changes. A row where something needed is empty gives an empty cell. A formula reads the columns of its own sheet only, by their short name. Only the rows in sight are drawn, so a hundred thousand rows scroll as ten do. Sorting moves whole rows. A formula has its own part of the panel and a button, Compute (Enter in the field does the same). One that names its own column (`B*2`, `B/max(B)`, `if(i == 1, A, B[i-1] + A)` for a running sum) is applied once to the numbers the column holds, row after row, and not kept: kept, it would be applied again at each change. Undo brings back what the column held. The selected cells are copied by Ctrl+C or by "Copy selection".

**Import.** Text files with columns (`.txt`, `.dat`, `.csv`…) and Tektronix RSA `.Specan` spectra, read in the browser: nothing is uploaded. The separator, the decimal mark (3.14 or 3,14), the lines of heading and the names of the columns are detected, shown with the first rows, and can be corrected before anything is kept. `Energy (eV)` in a heading becomes a title and a unit. A file dropped anywhere on the page opens the dialog.

Also read there, in the browser: the workbooks of Excel (`.xlsx`) and of LibreOffice or OpenOffice (`.ods`), a sheet of the project for each of their sheets, read from the first line as a text file is; and the projects of Origin (`.opj`), a sheet for each worksheet, with the long name, the unit and the role (X, Y, error) of each column. Any of the sheets can be left out before importing. The graphs of an Origin project are made again from those sheets, unless asked not to: a panel for each layer (a layer laid over another becomes its right axis), each curve on its columns as a line, symbols, both, bars or an area, with its colour, its line and its symbol; the ranges and the scales of the axes; their titles, with Origin's indices, exponents, Greek letters and special characters; the legend, the lines and the arrows; the texts, each where Origin keeps it (by its corner, or by its centre when it is centred; on the frame, outside it, or on the scales), in its colour, turned as it was, and as large beside the titles of the axes as it was. The functions drawn with "Add Function Graph" (a level `6.749`, a fitted curve `6.55+(6.68-6.55)*exp(-x/7.5)`, a steep line that stands for a vertical one) come as a sheet of their own, "functions": a column of x for each range, and each function as a column that keeps its formula, so that changing the formula or the x changes the curve. The size of the page and of the type are this page's own: a journal's format is then one choice away. What cannot be drawn here is said, in the dialog and under "What was done": a histogram (Origin counts it from the column), boxes, pies, contours and plots in three dimensions. The matrices, the notes and the report tables of a project are left. Not read, and said so with what to do: the `.opju` of Origin 2018 and later (save the project as `.opj`), the `.xls` of before 2007 (save it as `.xlsx`).

**Graphs.** A figure has a size in millimetres and type in points, and is shown as it will be printed. Symbols, lines, steps, bars, filled areas, error bars in x and y, a second y axis, logarithmic axes, several panels with a shared x axis, panel letters, a legend that can be dragged, texts, arrows, lines and highlighted ranges. Axis titles and labels take `E_{F}`, `cm^{-1}`, `\alpha`. The type sizes, the line widths, the direction and length of the ticks and the frame are set for the figure; an axis can have its own ticks (inwards, outwards, both, none; length; width), its own size of numbers and number of decimals, a title with its own size, in bold or italic, its colour (line, ticks, numbers and title together), small ticks or not, and a grid with its colour and its line. By hand, on the figure: the legend, the title of an axis, a text, a line, an arrow (by its middle or by one end) and a highlighted range (whole or by one edge) are dragged; a double-click on a name of the legend, the title of an axis, the title of a panel or a text rewrites it where it is. An arrow has one head or two, of a size that can be set. A panel title has its size, its colour, its place and can be bold. A figure has one font. Drag a rectangle to zoom, the wheel zooms about the pointer, double-click shows everything again. A long curve is thinned to what a page can show (50 000 points are drawn with about 5 700).

**Journals.** 28 presets set the width, the font, the type sizes and the line widths to what a journal asks (Nature, Science, ACS, APS, AIP, Elsevier, RSC, Springer, PNAS, IEEE; a slide; a thesis page). The style of a graph can be copied to another.

**Fits.** A model is a sum of components taken from a registry of 55 functions (peaks: Gaussian, Lorentzian, Voigt, pseudo-Voigt, Pearson VII, Moffat, split Lorentzian, bi-Gaussian, skewed and exponentially modified Gaussian, log-normal, Fano, Doniach–Šunjić, sinc²; baselines and polynomials; decays, alone or after a Gaussian pulse, growth, stretched exponential, power laws, logarithm; sigmoids, Hill, dose–response, Gompertz, Weibull; sines; Arrhenius, Langmuir, Michaelis–Menten, a Fermi–Dirac edge, alone or through a Gaussian resolution, Planck, the band gap against temperature of Varshni and of Bose–Einstein, thermal quenching with one or two channels, Langevin, Brillouin, Curie–Weiss, Vogel–Fulcher–Tammann, a diode, the derivative of a Lorentzian) or written as an expression (`a*exp(-x/tau) + c`). Each parameter has a starting value, can be held, bounded, or tied to others (`p2_center = p1_center + 3.2`). Starting values are read from the data (the baseline, then the most prominent peaks). Weights: none, 1/σ² from an error column, counting statistics, constant relative error. A range of x can be dragged on the graph. Several columns can be fitted one after the other, or together with shared parameters. Methods: Levenberg–Marquardt, trust region (with a robust loss against outliers), Nelder–Mead, Powell, differential evolution.

**Errors on both axes.** When x was measured too, its error column is counted with that of y: each point then counts by its distance to the curve in units of its two error bars (orthogonal distance regression), not by its vertical distance. A column of role "x error" placed after x is found by itself, drawn as horizontal bars, and taken by a new fit that has errors of y. Everything else stays as it is: bounds, ties, shared parameters, the band, the warnings.

**Through the response of the instrument.** A 56th entry of the registry, "Measured instrument response", is not a curve: with it in a model, the other components are convolved with a response measured on the same x as the data (a column of the sheet), and baselines are added afterwards. That is the fit of a decay measured by photon counting when the pulse is not short against it (iterative reconvolution). Its one parameter is the shift of the response along x, fitted like any other. A series gives each file its own response column.

**Which model.** A fit can be duplicated, its model changed, and fitted again. The results then say which of the fits of the same points the data support: AIC corrected for few points, BIC, the share of support of each (Akaike weights), and the F test of the fuller model against the simpler one, with the sentence that says when that test means something. On the graph each fit has its colour and its name.

**Series.** The same fit on many files: thirty spectra at thirty temperatures, and what is wanted is the position of a peak against temperature. The fit is made once, on one file. A series repeats it on the others: each file is given the same computed columns (the formulas, and the operations done again: a baseline removed, a smoothing), then fitted with the same model. The value of what was varied is read from the names of the files (`…_3kV_236nm_160K` → 160 K), shown, and can be corrected. The files are fitted from the one the fit was made on outwards, each starting from what its neighbour gave, so that a peak is followed as it moves; a neighbour whose fit carries a warning is not started from, and a file that ends with a warning is tried again from starting values read from its own data. What comes out is a sheet, one row per file: each parameter and derived quantity beside its uncertainty, ready to plot with its error bars and to fit in its turn, and a column that says which files to check. A file that cannot be fitted says why and the others go on. One graph shows each file with its fit, to look at them one by one; another draws all the files, coloured along what was varied and shifted to stack them. A curve of the results leaves out the files to check unless asked to draw them.

**What a fit is worth.** Every parameter with its standard error, and on request the interval found by profiling χ²; quantities derived from the parameters (width at half maximum, height, half-life…) with their uncertainty propagated through the covariance matrix; χ², reduced χ², R², AIC, BIC, and with true error bars the probability of the χ² found; correlations; the confidence band of the curve; a panel of residuals. And warnings in words when a number should not be trusted: a fit that did not converge, a parameter on its bound, two parameters the data cannot tell apart, error bars that are too small.

**The fit on its graph.** Under the Fit button: which of the components have their curve drawn, one button each; the curve of the fit hidden or shown; and what the fit writes on the graph, to choose among its equation (one line per component, as `y = A/(σ√(2π)) · exp(−(x−x_c)²/2σ²)`), its parameters with their uncertainty, the derived quantities, χ² and R². That text follows the fit: it is written again each time the fit is run, until it is rewritten by hand, after which it is the person's. It is dragged, sized and framed like any text.

**My formats.** The size, the type, the lines, the ticks and the colours of a graph can be kept under a name ("PRB single column", "my thesis") and given to any other graph, in any project of the same account. Without a server they are kept in the browser.

**For the paper.** The table of results as tab-separated text or LaTeX, a sentence for the methods ("The data were fitted with the sum of a Gaussian, a Lorentzian and a line by non-linear least squares…"), the equations of the model, and under "What was done" one line per operation with the values used.

**Operations.** 18 of them, each writing its result in new columns and saying what it did: Savitzky–Golay, moving average, median, Gaussian and Fourier filters; derivative, integral (area, centroid); baselines (asymmetric least squares, iterative polynomial, line between the ends); peak finding (position, height, prominence, width, area); normalisation, interpolation; Fourier transform; descriptive statistics, linear and polynomial regression, histogram; combining two curves.

**Export.** SVG and PNG are made by the page; PDF, EPS and TIFF by the server, from the same figure. The file has the size asked, to the hundredth of a millimetre, with its font embedded (TrueType, type 42). When the server does not hold the font asked for, the dialog says which one the file holds.

**Projects.** Sheets, graphs and fits are one project, saved a moment after each change, with undo. Two tabs cannot overwrite each other silently. A project can be saved to a file and opened again. A file the page writes (a project, a sheet as CSV, a figure) goes to the folder and under the name the person chooses, in a browser that lets a page ask (Chromium, on https or on localhost); elsewhere the browser puts it in its folder of downloads, and the page says so.

## How it is made

### The engine: `asymille/`

Plain Python over numpy, scipy, lmfit and matplotlib; no web framework, no database. It can be used from a script or a notebook.

| | |
|---|---|
| `expressions.py` | Arithmetic written by a person. Read by Python's parser and then walked: numbers, names, `+ - * / ^`, parentheses and 27 functions, nothing else. No `eval`. |
| `functions.py` | The registry of fit functions: label, family, equation, what each parameter means, starting values from the data, derived quantities. The line shapes are lmfit's. |
| `models.py` | A model as data (components and parameters), and its notation on one line: `p1:gaussian(center~5, sigma>0) + bg:linear()`. |
| `fitting.py` | `fit`, `fit_global`, `guess`, `evaluate`, `compare`. Minimising is lmfit's; statistics, propagation, bands, warnings, errors of x and the measured response are here. |
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
| `expr.js`, `importer.js`, `files.js`, `plot.js`, `model.js` | Logic without DOM: formulas, reading text files, reading spreadsheets and Origin projects, laying out a figure, the project. Run in Node by `tools/check_page.js`. |
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
- **Functions that hold an integral.** The decay after a Gaussian pulse and the Fermi edge through a Gaussian resolution are compared with the convolution they stand for, taken numerically: they agree to 10⁻⁹ and 10⁻¹², for a pulse from 5 000 times narrower to 6 times wider than the decay, and on both sides of the ratio of widths at which the edge changes how it is summed. Brillouin is compared with tanh (J = 1/2) and with Langevin (large J), the derivative of a Lorentzian with the Lorentzian's own slope, Planck's maximum with Wien's law.
- **Errors on both axes.** Pearson's data with York's weights, the line such methods are checked on: slope, intercept and χ² agree with the published values (−0.48053341, 5.47991022, 11.8663531941) to their last digit, and the standard errors with ODRPACK's (`scipy.odr`) to 10⁻⁶; York's own formula gives errors within 1 % of those. On two curves (a Gaussian, a decay) with scatter on both axes, parameters agree with ODRPACK's to 3·10⁻⁶ and standard errors to 3·10⁻⁵. On 40 noisy Gaussians whose error on x is a quarter of the peak's width, run once outside the tests: 22 ended at ODRPACK's χ² (parameters within 4·10⁻⁵), 17 at a lower one than ODRPACK with its default settings, 1 at a χ² higher by 3·10⁻⁶.
- **A decay through a measured response.** Two decays (1.2 and 6.0) convolved with a pulse 0.4 wide and a response shifted by 0.031: without noise, every parameter and the shift come back to 10⁻⁶, and the long decay also when only the part after the pulse is fitted; the reference convolution in the test is a plain sum written without the engine. With counting noise the two time constants come back within their uncertainties and the reduced χ² is near 1. Fitted without the response, the short decay is wrong.
- **Which model.** AIC and BIC of the comparison are the ones each fit shows; the F value is compared with its formula; two models 2 000 units of AIC apart are compared without overflow.
- **The confidence band.** On 40 simulated decays, a 95 % band covers the true curve at 93.4 % of its points on average (it is a pointwise band).
- **Operations.** Each on a curve whose answer is known: derivative and integral of sin, a Gaussian's area above its baseline, peaks of known width, a sine's amplitude by Fourier transform, regression against `scipy.stats.linregress`.
- **Figures.** A PDF has the size asked (to 0.01 pt), holds its font as TrueType, and is the same file when made twice. A figure laid out by the page is drawn by the server in three formats. The two were compared by eye on two figures: axes, ticks, labels and legend sit at the same places.
- **The two parsers.** The page's formula parser gives the same value as the server's on 28 expressions, and both refuse the same 25 texts: 20 that are not arithmetic, and 5 that are the formula of a column (`mean(a)`, `a[1]`, a condition), which a fit function must not be. What only a column reads is checked in Node on 19 formulas, empty cells included.
- **A series.** In Node, with a stand-in for the server: the columns found again in each file, the operation and the formula repeated, the order of the fits, the start from a neighbour, the second try, the table. In a browser, with the server: eight made-up files of a peak that moves with temperature, one of them with no peak at all. The seven with a peak gave its position within their uncertainty of the true one (8.240 for 8.24 at 20 K, 11.597 for 11.60 at 300 K); the one without was marked "to check" and the two files after it started from the last sound neighbour. Before that rule they started from the lost fit and ended at −224.
- **What a hand does on a figure.** In a browser, on the example, with the pointer: an arrow moved by its middle (both ends follow) and by its head (the other end stays), a line by one end, a highlighted range by one edge, the title of an axis dragged, a name of the legend, the title of an axis and a text rewritten by a double-click, also when the text was not the selected note. The buttons of a fit that show its components, its band and its panel of residuals take them away again, and the figure gets its height back. A part of a panel opened by hand stays open when a button redraws the panel. The figure so changed was drawn by the server.
- **Spreadsheets.** `tests/data/sample.xlsx` and `sample.ods` are written by openpyxl and by odfpy (`tools/build_spreadsheets.py`), not by this project: the page's reader gives the same two sheets from both, with names and units from the first line, an empty cell, a text among numbers, a sheet whose table starts at C3, and the 1 048 570 empty rows a spreadsheet writes after the last one.
- **Origin projects.** Read once, outside the tests, on ten projects of the test suite of LabPlot (Origin 8.0 to 9.95; they are not in this repository): all ten are read to the end. On the one for which that suite states the content cell by cell (`origin8_test_workbook.opj`: six columns of numbers and texts mixed), every cell agrees. A project of real measurements (81 columns, 250 to 273 rows) comes with its long names and each y beside its own x. Their graphs: the ranges of the axes are those that suite states for two of the projects (1.5 to 8.5 and 3.5 to 8.5), and the curve it names is on the columns it names; in a browser, a graph of green diamonds on a dashed line, bars, a fit drawn over its data, two layers one under the other and 54 curves with titles such as `k (Å⁻¹)` came out as curves on the right columns, with their colours, lines and titles. No picture made by Origin of those graphs was at hand to lay beside them. For one more project, of a user (not in this repository: measurements with their error bars and 22 functions), two pictures made by Origin were: the two graphs came out with the same curves, levels, fitted curve, dotted verticals, arrow and texts at the same places, in the same colours. One thing differed on one of the two: the picture shows the fitted curve up to 80 and two thick red strokes, where the file holds that function from 0 to 42 and no such strokes; the picture was most likely made from another state of the project. In the tests, a project built by the check itself, laid out as Origin lays one out: that checks the reader against what was understood of the format, not against Origin. The reference reader (liborigin) could not be built here to compare every value.
- **The fit on its graph.** The equation of each of the 56 entries of the registry on one line holds nothing the page cannot draw (a test reads the page's own list of Greek letters). In a browser: components drawn one by one, the text of the fit written, following a new fit, rewritten by hand and then left alone by the next fit; the server draws the framed text at the same place.
- **My formats.** Kept, replaced under the same name, refused beyond the limit, deleted; invisible to another account and gone with the account. In a browser: kept from one graph, given to another, there again after the page is loaded again.
- **Formulas applied once, and where files go.** In Node: a column doubled, divided by its own maximum and summed down its rows by a formula that names it, and left as it was by one that cannot be read. In a browser: the same through the button and through Enter, with a column that follows it computed again and Undo bringing the numbers back; the selection copied to the clipboard; a project saved through a stand-in for the browser's own window (the name suggested, the kind of file, what is written), nothing saved when that window is given up, and a download with a sentence when the browser has no such window. The window itself, which only a person can answer, was not driven.
- **The page, in a browser.** Driven with Playwright through the standalone server and through Ondelette's: import of the `.Specan` example, typing and pasting, a formula, plotting, fitting the example (centres found at 7.995 ± 0.006 and 14.494 ± 0.009 for 8 and 14.5), regression, zoom, undo, export to PDF, the list of projects, signing up. No error in the console. Through the standalone server only: a made-up decay of 600 points fitted through its response column (1.220 ± 0.010 and 6.04 ± 0.03 for 1.2 and 6.0), the same data fitted with one decay and the two compared, and York's line with its two error columns.

Not measured, or not done:

- **The journal presets were written from memory** of the guides for authors, not re-read from the publishers' sites. The page says so beside the preset. Check the width against the journal's current guide before submitting.
- **Fonts.** The server here has Liberation Sans, not Arial: the PDF holds Liberation Sans (the same metrics), and says so. Install Arial on the server for a file that holds Arial.
- **Page and server draw the same list, with their own text engines.** Positions are the same; the exact shape of a glyph, and the width of a text that is not anchored at its start, depend on the font each one has.
- **Errors on x need errors on y.** The two are counted together or not at all: a fit with errors on x alone is refused. The place of each point on the curve is found by at most twelve steps, each kept only if it brings the point nearer; on a model that bends within one error bar of x this is an approximation (the 3·10⁻⁶ above).
- **A measured response is for decays.** x must increase by even steps (to 2 %), the model is counted from the response and is nothing before it, and the response is used as it is: a constant background in it must be removed first (a formula does it), or the fit shows a baseline that rises. Widening a spectrum by a measured line is not done; for a Gaussian resolution there are functions that hold it (Voigt, the error-function step, the decay after a pulse, the Fermi edge). Errors on x cannot be counted with it.
- **Counting noise with few counts.** The weights 1/y underestimate a level of a few counts per channel (5 gave 3.8 in one trial): a known bias of that weighting, not corrected here.
- **Comparing models.** AIC and BIC are computed from χ² as lmfit does, which supposes residuals of one unknown variance. Whether one model is a special case of the other, which the F test needs, is for the person to know: it is said, not checked.
- **Origin functions.** A formula is computed by the page's own reader of formulas (arithmetic, powers and its list of functions): one that calls something else comes as an empty column, and the page says which. A function is drawn on the range and the number of points the file keeps for it.
- **Origin graphs.** The offset by which Origin draws stacked curves apart is not read (the file does not say it plainly): such curves are drawn without it, the page says so, and each can be shifted by hand. The size of the page, the fonts, the ticks and the grids of Origin are not taken: the page's are used, and a text keeps only its size beside that of the axis titles. A text that mixes sizes or colours takes one of each. A legend goes to the corner nearest to where it stood. Curved arrows, rectangles, circles and images on a graph are left.
- **Origin files.** Nothing was tried on a `.org` of Origin 4 or older (none was at hand): the reader takes it if it starts as an `.opj` does, and says so if it does not. Column types other than numbers and text (dates, times) come as the numbers Origin keeps. A project saved by a version later than 9.95 was not tried.
- **Spreadsheets.** A date comes as the number the spreadsheet keeps (Excel) or as its ISO text (LibreOffice). A cell holding a formula gives the value the spreadsheet last computed; a workbook never opened by a spreadsheet program has none. No file written by Excel itself or by LibreOffice itself was at hand: the two samples are written by libraries.
- **The equation on a graph is on one line**: fractions as a/b, exponentials as exp(…). The page draws one level of index or exponent, not a typeset formula; the typeset equations are in the Report.
- **Not in the fits.** A function defined by pieces or by a condition, by an integral or a differential equation of one's own, a surface z = f(x, y), several independent variables, an implicit function.
- **Speed.** No timing was measured beyond the tests. A fit is stopped after 30 s; it runs in the request, four at a time for all users.
- **Size.** A project travels whole at each save, data included. The host's limit on a request (4 MB in Ondelette) bounds it: about 200 000 numbers. The page says so when a save is refused.
- **A series keeps every file in the project**, so its size grows with them: eight files of 201 points made a project of 172 kB; thirty spectra of 4 000 points would be about 3 MB, near Ondelette's 4 MB. The dialog and the list of projects say how much room is left when the host says its limit. Only the parameters of each file are kept, not its fitted curve, which is computed again when the file is shown.
- **A series reads what was varied from the names of the files**, not from their headings. An operation that makes a table of its own (interpolation, Fourier transform) is not repeated by a series; those that write columns beside the data are.
- **No test drives the page's panels automatically**: `check_page.js` covers the logic without DOM; the browser sessions above were run by hand with a script, not kept as a suite.
- Not there: images placed in a figure (the previous application had them), a font per text, 3D and contour plots, date axes, Excel and binary instrument formats, a peak-by-peak "click to add" on the graph, reports as PDF, scripting by the user.

## Coming from the Django application

The stack was changed for the goal, not because Django is a lesser framework: Asymille is meant to live inside Ondelette (`Bigdft_ui`), which already has accounts, sessions and a database, on FastAPI and SQLAlchemy. Two frameworks do not share sign-in simply; one process, one database and one sign-in do. The engine is independent of that choice.

What the previous code did that this one must never do:

- **It ran what a user typed.** A custom fit expression went through `sympy.parse_expr`, which evaluates Python. `asymille/expressions.py` walks a syntax tree instead, and a test sends `__import__('os')` through the API.
- **It showed a fit of random numbers when the real one failed**, as if it were a result. A fit that cannot be made now says why.
- **Any signed-in user could list and change every account** (`UserViewSet`).
- **Secrets were in the repository**: Django's `SECRET_KEY` and the PostgreSQL password, in `my_saas_app/settings.py`, with `DEBUG = True`. They are still in the history of `main`: **change that password**.
- A whole virtualenv (254 MB), `__pycache__` and `.idea` were committed; a column expression was run with `Function(...)`; `ax` was read as `a*x`, so `exp(x)` became `e*x*p(x)`; a curve was only drawn at the data points.

`legacy/corentin_dap_decay.py` is kept untouched: a donor–acceptor pair recombination model with two integrals. It was not turned into a fit function, because the two integrals do not agree on the surface element (`r dr` in the first, `dr` in the second), and which one is meant is for its author to say.
