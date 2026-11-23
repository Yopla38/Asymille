#!/usr/bin/env node
/* The parts of the page that hold logic and no DOM, run in Node:
 *
 *     node tools/check_page.js            prints ok / FAILED per line, exits 1 on a failure
 *     node tools/check_page.js --write    also writes tests/data/project.json, which tests/test_api.py posts to the API
 *
 *   1  formulas (expr.js) give the values asymille/expressions.py gives for the same text (tests/data/expressions.json);
 *      the formula of a column reads more (whole columns, other rows, conditions), and a fit function is refused those
 *   2  the importer reads the example files, a European CSV, a file with a heading
 *   3  the project (model.js): formulas, sorting, undo; serialize and restore are exact inverses
 *   5  a series (model.js): the variable read from the names of the files, the same columns found in each file, the
 *      fit repeated from neighbour to neighbour with a stand-in for the server, and the table of what was found
 *   4  a figure (plot.js): ticks, markup, a layout whose every number is finite and inside the page, and what a
 *      person can change of an axis and of a title (ticks, numbers, colour, grid, size, place)
 *
 * The project it builds is the one the API is tested with: a field added to model.js that
 * asymille/web/schemas.py does not know fails there. */
'use strict';
const fs = require('fs'), path = require('path');
const ROOT = path.resolve(__dirname, '..');
global.window = {};
for (const f of ['util', 'expr', 'importer', 'plot', 'model']) require(path.join(ROOT, 'page/js', f + '.js'));
const A = window.ASY, M = A.model, P = A.plot;
A.fnLabel = (c) => c.fn;
let failed = 0;
const ok = (what, pass, detail) => { if (!pass) failed++; console.log((pass ? 'ok      ' : 'FAILED  ') + what + (pass || detail == null ? '' : '   ' + detail)); };
const close = (a, b, tol) => (a === b) || (a == null && b == null) || (typeof a === 'number' && typeof b === 'number' && (Math.abs(a - b) <= (tol || 1e-9) * Math.max(1, Math.abs(a), Math.abs(b)) || (isNaN(a) && isNaN(b))));
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');

// 1 ── formulas: the same text, the same value as the server's parser
const cases = JSON.parse(read('tests/data/expressions.json'));
let agree = 0;
for (const c of cases.values) {
  let got;
  try { got = A.expr.compile(c.text).run(cases.env); } catch (e) { got = 'error: ' + e.message; }
  const want = c.value === null ? NaN : c.value;
  if (typeof got === 'number' && (close(got, want, 1e-6) || (!isFinite(got) && !isFinite(want)))) agree++; else ok('formula ' + c.text, false, 'page ' + got + ', server ' + c.value);
}
ok(cases.values.length + ' formulas give the values of asymille/expressions.py', agree === cases.values.length);
let refused = 0;
for (const text of cases.refused) { try { A.expr.compile(text); ok('formula refused: ' + text, false, 'the page accepted it'); } catch (e) { refused++; } }
ok(cases.refused.length + ' texts that are not arithmetic are refused', refused === cases.refused.length);
// the formula of a column reads more than a fit function: whole columns, other rows, conditions
const table = { n: 5, cols: { A: [1, 2, 3, 4, 5], B: [10, 20, null, 40, 'n/a'] } };
const colOfText = (text) => A.expr.column(text).run(table).map((v) => (typeof v === 'number' && isFinite(v) ? Number(v.toPrecision(10)) : null)).join();
const formulas = { 'B/max(B)': '0.25,0.5,,1,', 'B - mean(B)': '-13.33333333,-3.333333333,,16.66666667,', 'sum(B) + count(B) + median(A) + min(A)': '77,77,77,77,77', 'sd(A)': Array(5).fill('1.58113883').join(), 'max(B - A)': '36,36,36,36,36',
  'max(A, 2.5)': '2.5,2.5,3,4,5', 'B - B[i-1]': ',10,,,', 'B/B[1]': '1,2,,4,', 'A[n] - A': '4,3,2,1,0', 'A[i+1] - A': '1,1,1,1,', 'A[1.5]': ',,,,', 'B > 15': '0,1,,1,', 'if(B > 15, A, -A)': '-1,2,,4,',
  'if(A >= 2 and not B == 20, 1, 0)': '0,0,,1,', 'A > 4 or A < 2': '1,0,0,0,1', 'if(A > 3, 1/0, 7)': '7,7,7,,', '(A > 1) + (A > 2)': '0,1,2,2,2', 'i*10 + n': '15,25,35,45,55', '2 and 0': '0,0,0,0,0' };
const wrong = Object.entries(formulas).filter(([text, want]) => colOfText(text) !== want).map(([text]) => text + ' → ' + colOfText(text));
ok(Object.keys(formulas).length + ' formulas of a column: of whole columns, of other rows, with conditions; an empty cell gives an empty cell', wrong.length === 0, wrong.join(' | '));
const said = (text, reader) => { try { A.expr[reader || 'column'](text); return ''; } catch (e) { return e.message; } };
ok('a formula that cannot be read says why', /condition, the value when it holds/.test(said('if(B > 1, 2)')) && /a < b and b < c/.test(said('1 < A < 3')) && /bracket is not closed/.test(said('B[1')) && /not expected here/.test(said('if + 1')) && /one: a whole column/.test(said('max(A, B, 3)'))
  && A.expr.column('B[i-1] + mean(C)').names.sort().join() === 'B,C,i');
ok('a fit function is told that these belong to columns, before the server refuses it', /for the formula of a column/.test(said('mean(a)', 'compile')) && /rows of a column/.test(said('a[1]', 'compile')) && /comparisons/.test(said('if(x > 1, a, b)', 'compile')) && /comparisons/.test(said('a > b', 'compile')));

// 2 ── reading files
const spectrum = A.importer.read(read('examples/NW1051-NW1.txt'), 'NW1051-NW1.txt');
ok('the example spectrum: 4001 rows, two columns named with their units', spectrum.rows === 4001 && spectrum.columns.length === 2 && spectrum.columns[0].title === 'Frequence' && spectrum.columns[0].unit === 'kHz' && spectrum.columns[1].unit === 'W' && close(spectrum.columns[1].values[0], 4.816006e-9));
const euro = A.importer.read('Mesure du 12/03\nTemps (s);Tension (mV);Note\n0,0;1,5;a\n0,5;2,25;b\n1,0;-3,0e-1;\n', 'euro.csv');
ok('a CSV with semicolons and decimal commas', euro.how.separator === 'semicolon' && euro.how.comma && euro.rows === 3 && euro.columns[1].values[1] === 2.25 && euro.columns[1].values[2] === -0.3 && euro.columns[2].values[0] === 'a' && euro.columns[2].values[2] === null && euro.columns[0].unit === 's', JSON.stringify(euro.how));
const spaced = A.importer.read('# instrument XYZ\n# T = 4 K\n#  x      y       err\n  1.0   2.0e3   0.1\n  2.0   NaN     0.1\n\n  3.0   4.0D3   0.2\n', 'spaced.dat');
ok('columns aligned with blanks, comment lines, NaN, a Fortran exponent', spaced.how.separator === 'space' && spaced.rows === 3 && spaced.columns.length === 3 && spaced.columns[1].values[1] === null && spaced.columns[1].values[2] === 4000 && spaced.columns[2].title === 'err', JSON.stringify(spaced.how) + JSON.stringify(spaced.columns.map((c) => c.title)));
const quoted = A.importer.read('name,"value, with comma",z\n1,2,3\n4,5,6\n', 'q.csv');
ok('a quoted CSV heading that holds the separator', quoted.columns.length === 3 && quoted.columns[1].title === 'value, with comma' && quoted.rows === 2);

// 3 ── the project
M.blank('Check');
const sheet = M.sheetFrom('Peaks', [{ title: 'Energy', unit: 'eV', values: [3, 1, 2, 4] }, { title: 'Counts', values: [30, 10, 'n/a', 40] }, { title: 'err', values: [1, 1, 1, 2], role: 'yerr' }]);
const twice = M.addColumn(sheet, { formula: 'B*2 + i' });
M.changed(sheet);
ok('a formula column is computed row by row, and a cell of text gives an empty one', JSON.stringify(twice.values) === '[61,22,null,84]', JSON.stringify(twice.values));
twice.formula = 'B/max(B) + A[1]'; M.recompute(sheet);
ok('a formula column reads a whole column and another row', JSON.stringify(twice.values) === '[3.75,3.25,null,4]', JSON.stringify(twice.values));
twice.formula = 'if(D > 1, 1, 0)'; M.recompute(sheet);
ok('a column cannot be computed from itself, in any way', /cannot be computed from itself/.test(M.errors[twice.id] || ''), M.errors[twice.id]);
twice.formula = 'B*2 + nope'; M.recompute(sheet);
ok('a formula that names no column says so', /no column is called nope/.test(M.errors[twice.id] || ''));
twice.formula = 'sqrt(A) + n'; M.recompute(sheet);
M.commit();
M.sortBy(sheet, sheet.columns[0], false); M.commit();
ok('sorting a sheet moves whole rows and recomputes the formulas', JSON.stringify(sheet.columns[0].values) === '[1,2,3,4]' && JSON.stringify(sheet.columns[1].values) === '[10,"n/a",30,40]' && close(M.sheet(sheet.id).columns[3].values[3], 6));
ok('undo brings back the order', M.undo() && JSON.stringify(M.sheet(sheet.id).columns[0].values) === '[3,1,2,4]' && M.redo() && JSON.stringify(M.sheet(sheet.id).columns[0].values) === '[1,2,3,4]');
const s = M.sheet(sheet.id);
ok('the x of a column is the X on its left, its error the yerr on its right', M.xOf(s, s.columns[1]) === s.columns[0] && M.errOf(s, s.columns[1]) === s.columns[2] && M.label(s.columns[0]) === 'Energy (eV)');
const graph = M.plot(s, [s.columns[1]], 'scatter');
const fit = M.addFit(s, s.columns[0], s.columns[1]);
fit.model.components = [{ id: 'p1', fn: 'gaussian', params: { center: { value: 2, vary: true, min: null, max: null, expr: '' } } }, { id: 'b1', fn: 'constant', params: {} }];
fit.limits = [0.5, null];
const cx = [1, 2, 3, 4];
fit.result = { success: true, redchi: 1, rsquared: 0.9, npoints: 3, params: [], derived: [], warnings: [], correlations: [], curve: { x: cx, y: [10, 20, 30, 40], components: { p1: [1, 2, 3, 4], b1: [9, 18, 27, 36] }, band: { level: 0.95, lower: [9, 19, 29, 39], upper: [11, 21, 31, 41] }, prediction: null }, residuals: { x: [1, 3, 4], y: [0.1, -0.1, 0] } };
M.showFit(fit, graph, { band: true, components: true }); M.showResiduals(fit, graph);
graph.figure.panels[0].y2 = P.axis({ label: 'Second (\\mu{}V)', color: '#d55e00', tickDir: 'out', tickSize: 7 });
Object.assign(graph.figure.panels[0], { title: 'Sample A', titleSize: 11, titleAlign: 'left', titleColor: '#0072b2', titleBold: true });
Object.assign(graph.figure.panels[0].x, { grid: true, gridColor: '#bbbbbb', gridDash: 'dot', minor: false });
graph.figure.panels[0].notes.push({ id: M.id('n'), type: 'text', x: 2, y: 30, text: 'T = 4 K', size: 8, coords: 'data' }, { id: M.id('n'), type: 'span', x: 1.5, x2: 2.5, color: '#e69f00', opacity: 0.2 });
// a series of two files, as it is kept: the project the API is tested with holds one
const second = M.sheetFrom('Peaks 180K', [{ title: 'Energy', unit: 'eV', values: [1, 2, 3, 4] }, { title: 'Counts', values: [12, 22, 33, 41] }, { title: 'err', values: [1, 1, 1, 2], role: 'yerr' }]);
const kept = M.addSeries(fit);
kept.variable = { name: 'Temperature', unit: 'K' }; kept.members[0].value = 160;
kept.members.push({ sheet: second.id, value: 180, state: 'done', message: '', result: { success: true, message: '', redchi: 1.2, rsquared: 0.98, npoints: 4, nvarys: 4, warnings: ['p1_sigma ended on its bound'],
  params: [{ name: 'p1_center', value: 2.1, stderr: 0.05, vary: true, tied: '' }], derived: [{ name: 'p1_fwhm', label: 'full width at half maximum', value: 1.4, stderr: 0.1 }] } });
M.seriesTable(kept); M.reviewGraph(kept);
M.log('Checked.'); M.doc.log.forEach((l) => { l.at = '2026-01-01T00:00:00.000Z'; });        // the same project at every run
M.commit();
const data = M.seriesData;
ok('a series of data reads its columns, with NaN where a cell is text', (() => { const d = data(graph.figure.panels[0].series.find((r) => r.kind === 'data')); return d.x.length === 4 && isNaN(d.y[1]) && d.yerr[3] === 2 && d.label === 'Counts'; })());
ok('the curves of a fit are series of the graph: total, band, components, residuals in a panel below', graph.figure.panels.length === 2 && graph.figure.panels[0].series.length === 5 && data(graph.figure.panels[1].series[0]).y.length === 3 && graph.figure.layout.shareX === true);
const written = JSON.stringify(M.serialize());
M.restore(JSON.parse(written));
ok('a project written and read back is the same project', JSON.stringify(M.serialize()) === written);
ok('what is sent to be fitted: null where a cell is not a number', JSON.stringify(M.fitData(M.fit(fit.id))) === '{"x":[1,2,3,4],"y":[10,null,30,40],"sigma":[1,1,1,2],"sigma_x":null,"response":null}');
{
  const f = M.fit(fit.id), err = f.yerr;                 // the error column stands here for the errors of x, then for a response
  f.xerr = err;
  const counted = M.fitData(f).sigma_x; f.options.weights = 'none';
  const ignored = M.fitData(f).sigma_x; f.options.weights = 'instrumental';
  f.model.components.push({ id: 'r1', fn: 'response', params: { shift: { value: 0, vary: true, min: null, max: null, expr: '' } } });
  let missing = ''; try { M.fitData(f); } catch (e) { missing = e.message; }
  f.response = err; f.limits = [2, 3];
  const d = M.fitData(f), ask = M.drawing(f, d, f.model, 50), cut = ask.cut({ x: ask.body.x, y: [5, 6, 7, 8], components: { p1: [1, 2, 3, 4] } });
  f.model.components.pop();
  const plain = M.drawing(f, M.fitData(f), f.model, 5);
  ok('the errors of x are sent with the weights that count errors, the response with a model that holds one', counted.join() === '1,1,1,2' && ignored === null && /choose the column that holds it/.test(missing)
    && d.response.join() === '1,1,1,2' && M.fitData(f).response === null && ask.body.x.join() === '1,2,3,4' && ask.body.response.join() === '1,1,1,2' && cut.x.join() === '2,3' && cut.y.join() === '6,7' && cut.components.p1.join() === '2,3'
    && plain.body.x.join() === '3,3,3,3,3' && plain.body.response === undefined);          // without a response: points spread over the range (here one usable point is in it)
  M.restore(JSON.parse(written));
}
{
  const both = M.sheetFrom('Both', [{ title: 'x', values: [1, 2] }, { title: 'sx', values: [0.1, 0.2], role: 'xerr' }, { title: 'y', values: [3, 4] }, { title: 'sy', values: [0.3, 0.4], role: 'yerr' }, { title: 'z', values: [5, 6] }]);
  const g2 = M.plot(both, [both.columns[2]], 'scatter'), drawn = M.seriesData(g2.figure.panels[0].series[0]), withBars = M.addFit(both, both.columns[0], both.columns[2]), without = M.addFit(both, both.columns[0], both.columns[4]);
  ok('a column of errors of x beside x is drawn as horizontal bars, and counted by a fit that has errors of y too', drawn.xerr.join() === '0.1,0.2' && drawn.yerr.join() === '0.3,0.4' && withBars.xerr === both.columns[1].id && M.fitData(withBars).sigma_x.join() === '0.1,0.2'
    && without.xerr === null && without.options.weights === 'none' && M.fitData(without).sigma_x === null);
  M.restore(JSON.parse(written));
}
{
  const f = M.fit(fit.id), g = M.graph(graph.id), tall = g.figure.height, all = M.shownOf(f);
  M.hideFit(f, 'components'); M.hideFit(f, 'band');
  const curveOnly = M.shownOf(f), kinds = g.figure.panels[0].series.map((r) => r.part || 'data').join();
  M.hideResiduals(f);
  const none = M.shownOf(f), one = g.figure.panels.length === 1 && g.figure.layout.shareX === false && g.figure.layout.ratios.length === 0 && g.figure.height === Math.round(tall / 1.25);
  // one component alone, the curve of the fit hidden and brought back, and what the fit writes on its graph
  const ids = f.model.components.map((c) => c.id), plainOf = (c) => 'y = ' + c.fn.toUpperCase() + '(x; \\sigma)';
  M.showFit(f, g, { components: [ids[1]] }); const oneOnly = M.shownOf(f).parts.join();
  M.showFit(f, g, { components: true }); M.hideFit(f, 'components', ids[0]); const allButFirst = M.shownOf(f).parts.join();
  M.drawTotal(f, false); const hidden = M.shownOf(f).total; M.showFit(f, g); const stillHidden = M.shownOf(f).total; M.drawTotal(f, true);
  M.hideFit(f, 'components');
  const wrote = M.writeFit(f, g, { equation: true }, plainOf), eq = wrote.text.split('\n');
  M.writeFit(f, g, { equation: true, params: true, stats: true }, plainOf); const full = wrote.text.split('\n'), same = M.fitNote(f).note === wrote && g.figure.panels[0].notes.filter((n) => n.fit === f.id).length === 1;
  const laid = P.layout(g.figure, M.seriesData).items.filter((it) => it.k === 'note:' + wrote.id), ys = laid.filter((it) => it.t === 'text').map((it) => it.y);
  wrote.frame = true; const framed = P.layout(g.figure, M.seriesData).items.filter((it) => it.k === 'note:' + wrote.id && it.t === 'poly').length;
  M.writeFit(f, g, {}, plainOf);
  ok('the components are drawn one by one; the curve of the fit stays hidden when asked; a fit writes its equation and what it found on its graph, in lines, and takes them away',
    oneOnly === ids[1] && allButFirst === ids.slice(1).join() && hidden === false && stillHidden === false && M.shownOf(f).total === true
    && eq.length === ids.length + 1 && eq[0] === 'y = ' + ids.map((k) => 'y_{' + k + '}').join(' + ') && eq[1].startsWith('y_{' + ids[0] + '} = ') && full.length > eq.length && /^reduced \\chi\^2 = /.test(full[full.length - 2]) && /^R\^2 = /.test(full[full.length - 1])
    && same && laid.filter((it) => it.t === 'text').length === full.length && ys.every((y, i) => i === 0 || y > ys[i - 1]) && framed === 1 && M.fitNote(f) === null
    && M.shownExpression('a*exp(-x/tau1) + x^2 - my_par*x_0') === 'a·exp(−x/\\tau_{1}) + x^{2} − my\\_par·x_0', [oneOnly, allButFirst, hidden, stillHidden, eq.length, full.length, laid.length, framed].join(' / '));
  M.showFit(f, g, { components: true, band: true }); M.showResiduals(f, g);
  ok('the components, the band and the panel of residuals of a fit are taken off the graph and put back; the curve of the fit stays', all.components && all.band && all.residuals && !curveOnly.components && !curveOnly.band && curveOnly.residuals && kinds === 'data,total'
    && !none.residuals && one && JSON.stringify(M.shownOf(f)) === JSON.stringify(all) && g.figure.panels.length === 2 && g.figure.height === Math.round(Math.round(tall / 1.25) * 1.25));
  M.restore(JSON.parse(written));
}
M.removeSheet(sheet.id);
ok('removing a sheet removes the series and the fits made of it', M.doc.fits.length === 0 && M.doc.graphs[0].figure.panels.every((p) => p.series.length === 0));
M.undo();
if (process.argv.includes('--write')) { fs.writeFileSync(path.join(ROOT, 'tests/data/project.json'), JSON.stringify(M.serialize(), null, 1) + '\n'); console.log('wrote   tests/data/project.json'); }
ok('tests/data/project.json is this project (run with --write after changing model.js)', fs.existsSync(path.join(ROOT, 'tests/data/project.json')) && JSON.stringify(JSON.parse(read('tests/data/project.json'))) === JSON.stringify(M.serialize()));

// 4 ── a figure
const T = (lo, hi, ax, len) => P.ticks(lo, hi, ax || {}, len || 200, 8, true);
ok('ticks: 0 to 10 by 2, minor ticks between', T(0, 10).major.map((m) => m.v).join() === '0,2,4,6,8,10' && T(0, 10).minor.length === 15);
ok('ticks: small numbers share a power of ten', T(1.2e-9, 5.6e-9).major.map((m) => m.runs[0].s).join() === '2,3,4,5' && T(1.2e-9, 5.6e-9).factor[1].s === '−9');
ok('ticks: a logarithmic axis counts in decades', T(0.5, 2e4, { scale: 'log' }).major.map((m) => m.runs[1].s).join() === '0,1,2,3,4' && T(0.5, 2e4, { scale: 'log' }).minor.includes(200));
ok('ticks: a step that was asked for', T(0, 1, { step: 0.25 }).major.map((m) => m.runs[0].s).join() === '0.00,0.25,0.50,0.75,1.00');
ok('ticks: negative numbers carry a true minus sign', T(-2, 2).major[0].runs[0].s === '−2');
ok('markup: subscripts, superscripts, Greek', JSON.stringify(P.runs('E_{F} (cm^{-1}) \\alpha\\mu{}m x^2')) === '[{"s":"E","v":0},{"s":"F","v":-1},{"s":" (cm","v":0},{"s":"−1","v":1},{"s":") αμm x","v":0},{"s":"2","v":1}]', JSON.stringify(P.runs('E_{F} (cm^{-1}) \\alpha\\mu{}m x^2')));
ok('text is measured with the widths of Helvetica', close(P.textWidth('0.5', 10), 13.9) && close(P.textWidth('Wide', 10), 9.44 + 2.22 + 5.56 + 5.56));
const g2 = M.graph(graph.id), list = P.layout(g2.figure, M.seriesData), W = g2.figure.width * P.MM, H = g2.figure.height * P.MM;
let bad = 0, numbers = 0;
for (const it of list.items) {
  const flat = it.t === 'line' ? it.paths.flat() : it.t === 'text' ? [it.x, it.y] : it.pts;
  for (const v of flat) { numbers++; if (typeof v !== 'number' || !isFinite(v)) bad++; }
  if (it.t === 'text' && !(it.x >= -1 && it.x <= W + 1 && it.y >= -1 && it.y <= H + 1)) { bad++; console.log('        off the page: ' + JSON.stringify(it)); }
}
ok('a figure laid out: ' + list.items.length + ' things to draw, every number finite, every text on the page', bad === 0 && numbers > 200 && list.hit.panels.length === 2, bad + ' bad');
const svg = P.svg(list);
ok('the figure as SVG: its size in millimetres, clips, text kept as text', svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg" width="120mm"') && svg.includes('<clipPath') && svg.includes('>Energy (eV)</tspan>') && !svg.includes('NaN') && !svg.includes('data-k'));
ok('what is sent to the server holds no key of the page', P.sendable(list).items.every((it) => !('k' in it)) && !('hit' in P.sendable(list)));
// what a person can change of an axis and of a title, each seen in what is drawn
const styled = (change) => { const f = P.defaults(); f.panels[0].series.push(P.series({ id: 'r1', type: 'line' })); f.panels[0].y2 = P.axis(); change(f, f.panels[0]); return P.layout(f, () => ({ x: [0, 1, 2, 3], y: [0, 10, 20, 30] })); };
const plainBox = styled(() => {}).hit.panels[0].box;
const outward = styled((f, p) => { p.y.tickDir = 'out'; p.y.tickLen = 6; p.y.tickWidth = 1.5; p.y.tickSize = 12; p.x.minor = false; });
const yTicks = outward.items.find((it) => it.t === 'line' && it.width === 1.5), xTicks = outward.items.find((it) => it.t === 'line' && it !== yTicks && it.paths.every((q) => q[0] === q[2]) && it.paths.length < 40 && !it.k);
ok('an axis with its own ticks: outwards, longer, thicker, larger numbers; the other axis as the page says', yTicks && yTicks.paths.some((q) => Math.abs(q[2] - q[0] + 6) < 0.02 || Math.abs(q[0] - q[2] + 6) < 0.02) && yTicks.paths.every((q) => Math.min(q[0], q[2]) >= outward.hit.panels[0].box.x - 6.01)
  && outward.items.some((it) => it.t === 'text' && it.size === 12 && it.k === 'yaxis:p1') && outward.items.some((it) => it.t === 'text' && it.size === 8 && it.k === 'xaxis:p1') && outward.hit.panels[0].box.x > plainBox.x + 5);
ok('small ticks can be left out of one axis', xTicks && xTicks.paths.length === 2 * P.ticks(-0.12, 3.12, {}, plainBox.w, 8, true).major.length);
const gridded = styled((f, p) => { p.x.grid = true; p.x.gridColor = '#ff0000'; p.x.gridDash = 'dash'; p.y.grid = true; f.stroke.grid = 0.8; });
ok('the grid of each axis has its colour and its line', gridded.items.some((it) => it.t === 'line' && it.stroke === '#ff0000' && it.width === 0.8 && JSON.stringify(it.dash) === '[3.2,1.6]') && gridded.items.some((it) => it.t === 'line' && it.stroke === '#d0d0d0' && !it.dash));
const coloured = styled((f, p) => { p.y2.color = '#d55e00'; p.y2.label = 'Right'; });
ok('an axis in a colour: its side of the frame, its ticks, its numbers and its title', coloured.items.filter((it) => it.k === 'frame:p1').length === 4 && coloured.items.filter((it) => it.k === 'frame:p1' && it.stroke === '#d55e00').length === 1
  && coloured.items.filter((it) => it.t === 'text' && it.color === '#d55e00').length > 3 && styled(() => {}).items.filter((it) => it.k === 'frame:p1').length === 1);
const labelled = (more) => styled((f, p) => { p.x.label = 'Energy (eV)'; p.y.label = 'Counts'; p.series[0].label = 'One'; Object.assign(p.x, more || {}); });
const xOf = (l) => l.items.find((it) => it.k === 'xlabel:p1'), at0 = xOf(labelled()), own = labelled({ labelSize: 14, labelBold: true, labelItalic: true, labelDx: 20, labelDy: -6.5, decimals: 2 }), at1 = xOf(own);
ok('the title of an axis has its own size, weight and slant, and sits where a hand moved it; the numbers have the decimals asked', at0.size === 9 && at0.weight === undefined && at1.size === 14 && at1.weight === 'bold' && at1.style === 'italic'
  && Math.abs(at1.x - at0.x - 20) < 0.5 && own.hit.panels[0].box.h < labelled().hit.panels[0].box.h - 5 && own.items.filter((it) => it.k === 'xaxis:p1').every((it) => /^\d\.\d\d$/.test(it.runs[0].s))
  && /font-style="italic"/.test(P.svg(own)) && !/font-style/.test(P.svg(labelled())) && P.sendable(own).items.some((it) => it.style === 'italic'));
const legendOf = labelled().hit.panels[0].legend, arrows = (more) => styled((f, p) => { p.notes.push(Object.assign({ id: 'n1', type: 'arrow', x: 0.5, y: 5, x2: 2, y2: 20, coords: 'data', width: 1 }, more)); });
const heads = (l) => l.items.filter((it) => it.t === 'poly' && it.k === 'note:n1'), wide = (l) => (P.svg(l, { keys: true }).match(/stroke-opacity="0" stroke-width="6"[^>]*data-k="(series|note):/g) || []).length;
ok('the legend says where each of its names is; an arrow has one head or two, of the size asked; on screen a thin line is doubled by a wide unseen one', legendOf.rows.length === 1 && legendOf.rows[0].id === 'r1' && legendOf.rows[0].label === 'One'
  && legendOf.rows[0].x > legendOf.x && legendOf.rows[0].y >= legendOf.y && heads(arrows({})).length === 1 && heads(arrows({ both: true })).length === 2
  && Math.abs(Math.hypot(heads(arrows({ head: 12 }))[0].pts[2] - heads(arrows({ head: 12 }))[0].pts[0], heads(arrows({ head: 12 }))[0].pts[3] - heads(arrows({ head: 12 }))[0].pts[1]) - 12) < 0.02
  && wide(arrows({})) === 2 && !/stroke-opacity="0"/.test(P.svg(arrows({}))));
const titled = styled((f, p) => { p.title = 'Sample A'; p.titleSize = 14; p.titleAlign = 'left'; p.titleColor = '#0072b2'; p.titleBold = true; });
const title = titled.items.find((it) => it.k === 'title:p1');
ok('a title with its size, its colour, its place, in bold', title.size === 14 && title.anchor === 'start' && Math.abs(title.x - titled.hit.panels[0].box.x) < 0.02 && title.color === '#0072b2' && title.weight === 'bold' && titled.hit.panels[0].box.y > plainBox.y + 14);
const barred = (err) => P.layout(Object.assign(P.defaults(), { panels: [Object.assign(P.panel('p1'), { series: [P.series({ id: 'r1' })] })] }), () => ({ x: [1, 2, 3], y: [8, 9, 10], yerr: err })).hit.panels[0].yr;
ok('error bars have their room on the axis, but one that dwarfs the data does not flatten the rest', barred([0.5, 0.5, 0.5])[1] > 10.5 && barred([0.5, 40000, 0.5])[1] < 11 && barred([0.5, 40000, 0.5])[1] > 10.5);
const beside = styled((f, p) => { p.legend.pos = 'out'; p.series[0].label = 'A long name for this curve'; });
ok('a legend set outside the panel has its room on the page', beside.hit.panels[0].legend.x >= beside.hit.panels[0].box.x + beside.hit.panels[0].box.w && beside.hit.panels[0].legend.x + beside.hit.panels[0].legend.w <= 120 * P.MM + 0.5 && beside.hit.panels[0].box.w < plainBox.w - 60);
const empty = P.layout(Object.assign(P.defaults(), { panels: [Object.assign(P.panel('p1'), { y: P.axis({ scale: 'log' }), series: [P.series({ id: 'r1' })] })] }), () => ({ x: [1, 2], y: [-1, -2] }));
ok('a logarithmic axis with no positive value is said, not drawn empty in silence', empty.hit.warnings.length === 1 && /none of its values is positive/.test(empty.hit.warnings[0]));
const long = Array.from({ length: 50000 }, (_, i) => i), dense = P.layout(Object.assign(P.defaults(), { panels: [Object.assign(P.panel('p1'), { series: [P.series({ id: 'r1', type: 'line' })] })] }), () => ({ x: long, y: long.map((v) => Math.sin(v / 50)) }));
const drawn = dense.items.find((it) => it.t === 'line' && it.k === 'series:r1').paths[0].length / 2;
ok('a curve of 50 000 points is drawn with ' + drawn + ': what a page can show', drawn < 8000 && drawn > 1000);

// 5 ── a series: the same fit on many files
(async () => {
  const names = M.variablesIn(['N3978_3kV_spot3_236nm_160K', 'N3978_3kV_spot3_236nm_180K', 'N3978_3kV_spot3_236nm_200K']);
  ok('what was varied is read from the names of the files: the number that differs, with its unit', names[0].values.join() === '160,180,200' && names[0].unit === 'K' && names[0].distinct === 3 && names[names.length - 1].distinct === 1
    && JSON.stringify(M.numbersIn('diaph2mm_int200s x-3 T=-5C')) === '[{"value":2,"unit":"mm"},{"value":200,"unit":"s"},{"value":3,"unit":""},{"value":-5,"unit":"C"}]');
  ok('names of different shapes: a number is known by its unit', M.variablesIn(['a 4K', 'b at 12 K, run 3', 'c 20.5K'])[0].values.join() === '4,12,20.5');

  M.blank('Series');
  const peak = (c) => [0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((x) => Math.round(100 * Math.exp(-((x - c) ** 2) / 2)) / 10);
  const file = (name, c) => M.sheetFrom(name, [{ title: 'Energy', unit: 'eV', values: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] }, { title: 'Counts', unit: 'a.u.', values: peak(c) }]);
  const s20 = file('run 20K', 4), s10 = file('run 10K', 3), s30 = file('run 30K', 5), s40 = file('run 40K', 6), s5 = file('run 5K', 2);
  const narrow = M.sheetFrom('one column', [{ title: 'only', values: [1, 2, 3] }]);
  // on the model sheet: a column made by an operation, a formula on it, and the fit of that formula column
  const base = M.addColumn(s20, { title: 'Baseline removed of Counts', values: peak(4).map((v) => v - 1), made: { op: 'baseline_line', args: { points: 2 }, x: s20.columns[0].id, y: s20.columns[1].id, y2: null, part: 1 } });
  const twiceOf = M.addColumn(s20, { formula: base.name + '*2' }); M.changed(s20);
  const fit2 = M.addFit(s20, s20.columns[0], twiceOf);
  fit2.model.components = [{ id: 'p1', fn: 'gaussian', params: { amplitude: { value: 1, vary: true, min: null, max: null, expr: '' }, center: { value: 4, vary: true, min: null, max: null, expr: '' }, sigma: { value: 1, vary: false, min: 0, max: null, expr: '' } } }];
  fit2.options.started = true;
  const sr = M.addSeries(fit2);
  ok('a sheet that lacks the columns the fit reads cannot be in the series, and is told why', /1 column of data where “run 20K” has 2/.test(M.fitsIn(sr, narrow)) && M.fitsIn(sr, s30) === '');
  [[s10, 10], [s30, 30], [s40, 40], [s5, 5]].forEach(([s, v]) => sr.members.push({ sheet: s.id, value: v, state: 'todo', message: '', result: null }));
  sr.members[0].value = 20;
  ok('the files are fitted from the model sheet outwards, each after its neighbour', M.seriesOrder(sr).map((o) => o.member.value + '<' + (o.from ? o.from.value : '')).join(' ') === '20< 30<20 40<30 10<20 5<10' && M.commonName(['PL_sampleA_100K', 'PL_sampleA_20K']) === 'PL_sampleA' && M.commonName(['a1', 'b2']) === '');
  // a stand-in for the server: an operation subtracts 1, a fit finds the centre where y is largest, refuses the file at 40 K and warns about the one at 10 K
  const asked = [];
  const call = async (path, body) => {
    asked.push({ path, body: JSON.parse(JSON.stringify(body)) });
    if (path === 'asymille/analyse') return { sheet: 'same', note: 'Line removed.', columns: [{ name: 'Baseline', values: body.y.map(() => 1) }, { name: 'Baseline removed', values: body.y.map((v) => v - 1) }], facts: [] };
    if (path === 'asymille/model/guess') return { model: body.model };
    const top = body.x[body.y.indexOf(Math.max(...body.y))];
    if (top === 6) throw new Error('the server refused this one');
    return { success: true, message: '', redchi: 1, rsquared: 0.99, npoints: body.x.length, nvarys: 2, warnings: top === 3 ? ['p1_center ended on its bound'] : [],
      params: [{ name: 'p1_amplitude', value: 9, stderr: 0.1, vary: true }, { name: 'p1_center', value: top, stderr: 0.02, vary: true }, { name: 'p1_sigma', value: 1, stderr: null, vary: false }],
      derived: [{ name: 'p1_fwhm', label: 'width', value: 2.35, stderr: null }], curve: { x: [0, 9], y: [0, 0], components: { p1: [0, 0] } } };
  };
  const told = [];
  const table = await M.runSeries(sr, call, (m) => told.push(m.value + ':' + m.state));
  const centreSent = (a) => a.body.model.components[0].params.center.value, fitsOf = (s) => asked.filter((a) => a.path === 'asymille/fit' && a.body.y.join() === s.columns[3].values.join());
  ok('each file is given the columns the model sheet computes: the operation done again, then the formula', [s10, s30, s40, s5].every((s) => s.columns.length === 4 && s.columns[2].made && s.columns[2].made.op === 'baseline_line' && s.columns[2].made.y === s.columns[1].id && s.columns[3].formula === twiceOf.formula)
    && s30.columns[3].values.every((v, i) => close(v, (peak(5)[i] - 1) * 2)) && asked.filter((a) => a.path === 'asymille/analyse').length === 4, JSON.stringify(s30.columns.map((c) => c.name + ':' + (c.made ? c.made.op : c.formula))));
  ok('a file starts from what its neighbour gave, and the held parameter stays held', centreSent(fitsOf(s20)[0]) === 4 && centreSent(fitsOf(s30)[0]) === 4 && centreSent(fitsOf(s40)[0]) === 5 && centreSent(fitsOf(s10)[0]) === 4
    && fitsOf(s40)[0].body.model.components[0].params.sigma.vary === false && fitsOf(s30).length === 1, [s20, s30, s40, s10].map((s) => centreSent(fitsOf(s)[0])).join());
  ok('a fit that carries a warning is tried again from its own data, and the next file does not start from it', fitsOf(s10).length === 2 && asked.filter((a) => a.path === 'asymille/model/guess').length === 1 && fitsOf(s5).length === 1 && centreSent(fitsOf(s5)[0]) === 4,
    fitsOf(s10).length + ' ' + centreSent(fitsOf(s5)[0]));
  const mOf = (v) => sr.members.find((m) => m.value === v);
  ok('a file that cannot be fitted says why, and the others are fitted all the same', mOf(40).state === 'failed' && /refused this one/.test(mOf(40).message) && mOf(40).result === null && [5, 10, 20, 30].every((v) => mOf(v).state === 'done') && told.join(' ').includes('40:running') && told[told.length - 1] === '5:done');
  const colOf = (key) => table.columns.find((c) => c.made && c.made.key === key);
  ok('what was found is a sheet: a row per file in the order of what was varied, each parameter beside its uncertainty', colOf('variable').values.join() === '5,10,20,30,40' && colOf('variable').role === 'x' && colOf('p1_center').values.join() === '2,3,4,5,' && colOf('p1_center').unit === 'eV'
    && colOf('p1_center:err').role === 'yerr' && table.columns.indexOf(colOf('p1_center:err')) === table.columns.indexOf(colOf('p1_center')) + 1 && !colOf('p1_sigma') && colOf('p1_fwhm').values[2] === 2.35 && M.errOf(table, colOf('p1_center')) === colOf('p1_center:err'));
  ok('the rows that should not be trusted are marked: the one that failed, the one with a warning', /refused this one/.test(colOf('check').values[4]) && colOf('check').values[1] === '1 warning' && colOf('check').values[0] === null && colOf('file').values[1] === 'run 10K');
  const ids = table.columns.map((c) => c.id).join(), graphOf = M.plot(table, [colOf('p1_center')], 'both'), trend = graphOf.figure.panels[0].series[0];
  trend.unless = colOf('check').id;
  const left = M.seriesData(trend);
  ok('a curve of the results can leave out the files marked to check, which stay in the sheet', left.x.join() === '5,20,30' && left.y.join() === '2,4,5' && left.left === 2 && colOf('p1_center').title === 'p1 center' && graphOf.figure.panels[0].y.label === 'p1 center (eV)');
  trend.unless = null;
  sr.chain = false; asked.length = 0;
  await M.runSeries(sr, call);
  ok('run again, the table is the same sheet and the same columns: a graph made of it follows', M.sheet(sr.results) === table && table.columns.map((c) => c.id).join() === ids && M.seriesData(graphOf.figure.panels[0].series[0]).yerr[2] === 0.02
    && asked.filter((a) => a.path === 'asymille/fit').every((a) => centreSent(a) === 4) && [s10, s30].every((s) => s.columns.length === 4));
  const review = M.reviewGraph(sr); sr.current = s30.id;
  const shownData = M.seriesData(review.figure.panels[0].series[0]), shownFit = M.seriesData(review.figure.panels[0].series[1]);
  ok('a graph shows one file of the series at a time, with the curve fitted to it', shownData.y.join() === s30.columns[3].values.join() && shownData.label === 'run 30K' && P.literal('PL_sampleA^2') === 'PL\\_sampleA\\^2' && P.plain(P.literal('PL_sampleA_20K')) === 'PL_sampleA_20K' && shownFit && shownFit.x.join() === '0,9' && M.reviewGraph(sr) === review);
  const all = M.overlayGraph(sr, 5).figure.panels[0].series;
  ok('every file on one graph, coloured along what was varied, each shifted from the one before', all.length === 5 && all.map((r) => r.label).join() === '5,10,20,30,40' && all[0].color === '#440154' && all[4].color === '#e8d51c' && M.seriesData(all[3]).y[0] === s30.columns[3].values[0] + 15, all.map((r) => r.label + r.color).join());
  const mark0 = M.mark(fit2); fit2.model.components[0].params.center.value = 4.5;
  const sameMark = M.mark(fit2) === mark0; fit2.limits = [1, 8];
  ok('a series knows the model it was run with: a starting value does not change it, a range does', sameMark && M.mark(fit2) !== mark0 && sr.ran === mark0);
  // through a response: each file sends its own column, found as the fit's other columns are
  const marked = M.mark(fit2);
  fit2.model.components.push({ id: 'r1', fn: 'response', params: { shift: { value: 0, vary: true, min: null, max: null, expr: '' } } }); fit2.response = s20.columns[1].id;
  const own = M.memberData(sr, s30).response.join() === s30.columns[1].values.join() && M.fitsIn(sr, narrow) !== '' && M.mark(fit2) !== marked;
  fit2.model.components.pop(); fit2.response = null;
  ok('a file of a series sends its own response of the instrument, and the series knows the response is part of what it was run with', own && M.mark(fit2) === marked);
  const copy = M.duplicateFit(fit2), result = (chisqr) => ({ ndata: 10, nvarys: 2, chisqr });
  const before = M.comparable(fit2, copy); fit2.result = result(4); fit2.stale = false; copy.result = result(3);
  const both = M.comparable(fit2, copy) && M.comparable(copy, fit2) && !M.comparable(fit2, fit2); copy.limits = [0, 1];
  ok('a copy of a fit is another fit of the same points: the two can be compared once both are fitted, not when their ranges differ', !before && both && !M.comparable(fit2, copy) && copy.name !== fit2.name && copy.id !== fit2.id && M.doc.view.fit === copy.id);
  const text = JSON.stringify(M.serialize()); M.restore(JSON.parse(text));
  const old = JSON.parse(text); delete old.series; old.sheets.forEach((s) => s.columns.forEach((c) => { delete c.made; })); old.fits.forEach((f) => { delete f.xerr; delete f.response; });
  ok('a project with a series written and read back is the same; one saved before there were series, errors of x or responses opens', JSON.stringify(M.serialize()) === text && M.restore(old) && M.doc.series.length === 0 && M.doc.sheets[0].columns[0].made === null && M.doc.fits[0].xerr === null && M.doc.fits[0].response === null);
  console.log(failed ? '\n' + failed + ' FAILED' : '\nall ok');
  process.exit(failed ? 1 : 0);
})();
