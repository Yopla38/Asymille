# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Asymille: curve fitting, data analysis and figures for publication, in a browser (what Origin does between a measurement and a paper). An engine in plain Python (`asymille/`), an API for a host that brings the accounts (`asymille/web/`), and a page of plain scripts (`page/`). It is meant to live inside Ondelette (the repository `Bigdft_ui`), whose stack and charter it follows; `serve.py` runs it alone, for one person. The README says what it does, how it is made, and what was measured. Everything is written in English.

`main` still holds the Django application this replaces. `legacy/` is kept untouched.

## Commands

```bash
uv sync
uv run python serve.py                    # http://localhost:8780, one local user, data/asymille.db
uv run pytest                             # the engine, the API, the figures (no browser, no network)
uv run pytest tests/test_fitting.py -k nist        # one file, one test
uv run mypy && uv run ruff check asymille tests tools serve.py
node tools/check_page.js                  # the page's logic in Node: prints ok / FAILED per line, one pass
node tools/check_page.js --write          # also rewrites tests/data/project.json (see below)
uv run python tools/build_expressions.py  # rewrites tests/data/expressions.json from asymille/expressions.py
uv run --with openpyxl --with odfpy python tools/build_spreadsheets.py    # rewrites tests/data/sample.xlsx and sample.ods (those two libraries are for this only)
```

Run `pytest` and `mypy` after a change in `asymille/`; `check_page.js` after a change in `page/js/expr.js`, `importer.js`, `files.js`, `plot.js` or `model.js`. There is no automated test of the panels: after a change in `grid.js`, `figview.js`, `inspect.js`, `fitpanel.js`, `dialogs.js` or `app.js`, open the page (Chromium and Playwright are enough) and look.

## Architecture

### Three layers, one direction

`page/` → `asymille/web` → `asymille/`. The engine imports no web framework and no database; `asymille/web` imports the engine; the page calls the API. Keep it so: the engine is also used from scripts.

### The registries are the single source

`asymille/functions.py` (fit functions) and `asymille/analysis.py` (operations) are registries: each entry holds what a person needs (label, family, equation or summary, arguments with bounds and help) and the function itself. The page reads them once (`GET …/catalogue`) and draws its lists and forms from them. To add a fit function or an operation, write it in Python with `F(...)` or `@O(...)`: nothing is written in JavaScript. A test runs every entry of both registries.

### A figure is a list of things to draw

`page/js/plot.js` `layout(figure, data)` turns a figure (millimetres, points, axes, series) into a list of items: `line`, `poly`, `marks`, `text`, in points, y downwards. `svg(list)` writes it for the page; `asymille/figures.py` draws the same list with matplotlib for PDF, EPS, TIFF and PNG. The server decides nothing about a figure. So:

- a change of how a figure looks goes in `layout`, never in `figures.py`;
- a new kind of item must be added to both `svg()` and `figures._draw`, and `tests/test_figures.py::test_the_page_and_the_server_draw_the_same_list` runs the real layout through the server;
- symbols are drawn within ±0.5 of their size because matplotlib scales a custom marker to that;
- text width is estimated from Helvetica's widths (`WIDTHS` in `plot.js`), not measured in the DOM: `plot.js` has no DOM and runs in Node.

### The project is one document, described twice

`page/js/model.js` holds the project (`serialize` and `restore` are inverses) and `asymille/web/schemas.py` describes the same shape and refuses unknown fields. A field added to the document must be added to `ProjectDocument`, or every save fails with 422. `tools/check_page.js --write` writes `tests/data/project.json` from the model and `tests/test_api.py` posts it: that pair is what catches a drift. The parts only the page reads (`figure`, `result`, `options`, `view`) are free dictionaries there on purpose. Never dump the document with `exclude_none`: an empty cell is a meaningful null.

A fit result is kept in the project, so a project opened again shows what was found without computing. `stale` says the data or the model changed since.

### A series is a fit repeated on many sheets

`doc.series` holds series of files (`page/js/model.js`, "series: the same fit on many files"); a graph's own `panel.series` are its curves, an older use of the word kept in the document. The page says "Series" for the first and "Curves" for the second.

A series names a fit and member sheets, each with the value of what was varied. `runSeries(sr, call, tell, stop)` is in `model.js`, without DOM, with the server injected as `call(path, body)`: `tools/check_page.js` runs it with a stand-in. Things it relies on:

- a column made by an operation keeps how (`column.made = {op, args, x, y, y2, part}`, set by `app.analyse`); `counterpart(from, cid, to)` finds what a column of the model sheet is in another sheet: the same place among imported columns, the same formula, the same operation on its own counterparts. `replay` gives each member the computed columns, with the same short names so that formulas read them;
- the order is from the model sheet outwards, and a file starts from its neighbour only when that neighbour's fit is `sound` (converged, no warning); otherwise from the last sound one on that side. A fit that is not sound is tried once more from `model/guess` on its own data. Do not weaken this: one file without a peak used to send every file after it astray;
- a member keeps `brief(result)` only (parameters, derived, statistics, warnings): thirty full results would not fit in a project. The curve of the file shown lives in `memberCurves` for the visit and is computed again by `model/evaluate`;
- the table of results is a sheet rebuilt in place: its columns are found again by `made = {series, key}`, so their ids, and the graphs made of them, survive a new run. A row to check keeps its numbers and is marked in the `check` column; a curve with `unless` set to that column leaves those rows out.

### Nothing the page sends is executed

An expression (a custom fit function, a tie between parameters) is parsed by `ast.parse` and then walked by `asymille/expressions.py`: numbers, names, `+ - * / ^`, calls of a fixed list of functions. No `eval`, no `sympy.parse_expr`, no attribute access; every number is a float. A tie is checked by that walker before lmfit's own evaluator sees it. A model names functions of the registry; an operation is called by its name. Do not add an endpoint that runs what it receives. The page has its own parser (`page/js/expr.js`, no `eval` or `Function` either) with two readers. `compile` reads exactly what the server reads, and `tests/data/expressions.json` holds the cases both must agree on: the fit panel checks a custom function with it, so the page never accepts what the server will refuse. `column` reads that and what only the formula of a column needs (functions of a whole column, `B[i-1]`, comparisons, `and`/`or`/`not`, `if`): computed in the page, never sent, and refused by `compile` and by the server alike (`REFUSED` in `tools/build_expressions.py` holds examples). Do not add these to `asymille/expressions.py` to make the two alike: a fit function has no rows. In `column`, an empty cell is NaN and stays NaN through comparisons and `if`; an aggregate is computed once per run (`e.kept`). A formula that names its own column is never kept (`recompute` refuses it): `model.applyOnce` runs it once with `self`, which writes each row as it is computed, so that a row reads what the rows above it have become, and leaves numbers.

### Fitting

`fitting._solve` builds lmfit parameters, minimises, then always ends with a `least_squares` descent with a central-difference Jacobian and tight tolerances (`TOLERANCE`): that last step is what makes the NIST tests pass at 1e-6. `gtol` is disabled on purpose (it is absolute, and stops at once on data of small magnitude). Uncertainties of derived quantities and of the curve come from `_propagate` (finite differences through the covariance matrix, ties followed). A refusal is a `FitError` whose message is written for the person: the API passes it on as it is.

Everything that compares the model with data goes through two functions of `fitting.py`: `_at(model, params, data)` (the model at the points of a dataset) and `_residual` (model minus data in units of the error bars). Call them, not `model.evaluate` on `data.x`, or a new feature will ignore the two things a dataset may bring:

- **errors of x** (`Data.sx`): `_residual` then moves each point along x to the nearest place of the curve (guarded Gauss–Newton steps from 0) and returns that distance, signed. The tests hold it to York's line and to ODRPACK's numbers, written in the tests: `scipy.odr` is deprecated and is not imported;
- **a measured response** (`Data.grid`, `kernel`, `index`): the model is computed on every x of the measurement, convolved, and read at the fitted points, so that a range that starts after the pulse still sees the pulse. The response is a component of the model (`fn: "response"`, kind `response` in the registry) whose only parameter is its shift: that is what makes the shift a parameter like the others in the panel, the one-line notation, ties and series. `Model.convolved(c)` says which components it acts on (all but baselines); its own curve is zero and is left out of what is drawn (`_shown`).

`compare` takes numbers the page already holds (points, fitted parameters, χ²) and decides nothing about which fits may be compared: `comparable` in `page/js/model.js` does (the same columns, range, weights and loss).

### What a fit puts on its graph

A registry entry carries its equation twice: `tex`, typeset in the panel and the report, and `plain`, one line in the markup `plot.js` draws (`x_c`, `^{2}`, `\sigma`). `plain` is written from `tex` by `functions.one_line`; what that cannot write (cases, sums, integrals) is given by hand as `plain=`. A test holds every `plain` to what the page can draw, reading the Greek letters from `plot.js` itself: a new function whose equation uses another TeX command fails there, and wants a `plain=`.

The text a fit writes on a graph is a note of the figure (`type: 'text'`, several lines) that names its fit (`fit`) and what it holds (`of`). `model.refreshFitNotes` writes it again after each fit; a text edited by hand loses `fit` and is left alone. A fit has one such text, on one graph (`fitNote`); it is empty until there is something to write (no component, or parameters asked before the fit is run), and `fitpanel.writtenWhere` then says why, or on which graph it is (`bringFitNote` moves it). The curve of the fit is hidden with `show: false`, not removed, so that `showFit` after a new fit does not bring it back.

### Files that are not text

`page/js/files.js` reads `.xlsx`, `.ods` and Origin's `.opj` in the browser: nothing is sent. A spreadsheet becomes tab-separated text and goes through `importer.js` like any file, so headings and units are detected the same way. The Origin reader follows what liborigin found of an undocumented format: datasets, then windows whose "curves" are the columns of a worksheet. The windows are read inside a `try`: a file whose windows are laid out otherwise still gives every value. A window that is not a worksheet is a graph: `graphOf` turns its layers into a description that names tables and columns by their place (no ids of this project), and `model.graphFrom(spec, sheetOf)` makes the graph from the sheets that were imported; a curve whose sheet was left out is left. A function drawn on a graph (a dataset whose type has bit `0x80`: a formula of x, a first x, a step, a count) becomes a column of a sheet "functions" that carries `fx` (the formula) and `on` (the place of its column of x): `model.sheetFrom` turns that into a live formula on the short name the x column gets. A text is placed by the two numbers the file keeps at `0x13` and `0x1b` of its header, not by its box: fractions of the frame, or values of the axes when it is tied to the scales; the top left corner of the block, or its centre when the text is centred (`d1[8]` not zero). A note of a figure therefore has `anchor`, `valign` (`top`, `middle`, or the baseline of the first line) and `rotate`, read by `plot.js`. `originText` writes Origin's rich text (`\+(2)`, `\g(m)`, `\(x03C7)`) in the markup of `plot.js`, and escapes `_` and `^` that are not markup: long names of columns go through it too. It was checked on real projects that are not in the repository (the README says which); the check in `check_page.js` builds its own project, so it guards the reader's logic, not the format. Do not add a server route that parses uploaded files: these readers run where the file is.

### The host

`asymille/web/host.py` is what Asymille asks of a server: its declarative base, the owner column, a session, who is signed in, how to raise an error. `build(host)` defines the two tables (`asymille_projects`, and `asymille_formats`: the formats of a figure a person kept under a name) on the host's base and returns the router. Every query on a project or a format carries `owner_id` in the statement itself; one of someone else is a 404. A table added in `tables.py` needs a migration in the host: `Bigdft_ui` has one per table. `standalone.py` is the smallest host (one user, SQLite, tables made with `create_all`); Ondelette's is `backend/app/asymille.py` in `Bigdft_ui`, with a migration.

`page/shared/api.js` is a verbatim copy of Ondelette's `prototype/js/api.js`; `page/shared/account.js` is a stand-in used only by `serve.py`. In Ondelette the page loads Ondelette's own two files instead, and `Bigdft_ui/backend/update_from_asymille.sh` copies `asymille/`, `page/index.html`, `page/js/` and the example file there unchanged. So: nothing in `asymille/` or `page/js/` may import or assume Ondelette, and nothing there may assume the standalone server either.

### The page

`index.html` is written as page content, without doctype or `<html>` (the host wraps it and gives inline scripts a nonce): open it through a server, not from the file system. Scripts attach to `window.ASY` and load in dependency order. `app.touch()` commits and redraws everything but the inspector (a field was edited in it); `app.refresh()` redraws all. Controls of `ASY.ui` write to the project on `change` and call one of the two. `ASY.fill(el, …)` replaces children and skips nulls: `Element.replaceChildren` would write the text "null". A file the page writes goes through `ASY.saveAs(name, mime)`: it asks the browser where (when it can) before the file is made, because that window needs the click to be recent, and falls back to a download.

Three things that were bugs once:

- a panel is built again at each `refresh`, so a `<details>` must not be written with a fixed `open`: `ui.sec` and `ui.fold` remember what a person opened or closed (by tab and title), and `open` is only how it starts;
- `figview.js` captures the pointer on `pointerdown`, so the `click` and `dblclick` that follow name the paper, not the text under the pointer: ask `document.elementFromPoint`. And the SVG must not be written again between the two clicks of a double-click (the browser then drops it): a click redraws the figure only when it changes what is selected, and a drag starts after two points of travel;
- a curve or the line of a note is a hair wide: `svg(list, {keys: true})` doubles it with a wide unseen line that takes the pointer. It is for the screen: `sendable` and a `svg` without `keys` do not hold it.

## Conventions

- The README states counts and measured facts (55 functions and the instrument response, 18 operations, 28 presets, 149 tests, 77 check lines, the NIST tolerances). When a change moves one, update the sentence, and say what was measured and what was not in the same plain register.
- The journal presets in `asymille/journals.py` are written by hand from the guides for authors; `CHECKED` says they were not re-read from the publishers. Do not present them as verified unless they were.
- A result is never invented: a fit that fails says why, an operation that cannot be done says why, and a warning is attached to a number that should not be trusted.
- Commit subjects are one plain sentence saying what changed.
