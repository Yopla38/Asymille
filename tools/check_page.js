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
for (const f of ['util', 'expr', 'importer', 'files', 'plot', 'model']) require(path.join(ROOT, 'page/js', f + '.js'));
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
const mine = Object.assign(P.defaults(), { width: 86, height: 60, font: 'Helvetica', journal: 'aps-1', frame: 'open' }); mine.size.label = 7; mine.stroke.line = 0.8; mine.tick.dir = 'out'; mine.panels[0].x.label = 'Only here';
const taken = P.applyFormat(P.defaults(), JSON.parse(JSON.stringify(P.formatOf(mine))));
const wary = P.applyFormat(P.defaults(), { width: 'wide', height: -5, font: 12, size: { label: '9', tick: 6.5, evil: 1 }, stroke: 'thick', panels: [], layout: { cols: 9 }, journal: null, __proto__: { frame: 'open' } });
ok('a format kept from a figure gives another its size, its type, its lines and its ticks, and nothing else; what is not a format is not taken', JSON.stringify(P.formatOf(taken)) === JSON.stringify(P.formatOf(mine)) && taken.panels[0].x.label === ''
  && Object.keys(P.formatOf(mine)).join() === P.FORMAT.join() && wary.width === 120 && wary.height === 85 && wary.font === 'Arial' && wary.size.label === 9 && wary.size.tick === 6.5 && wary.size.evil === undefined && wary.stroke.line === 1.2
  && wary.panels.length === 1 && wary.layout.cols === 1 && wary.journal === null);
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
  // ---- files that are not text: spreadsheets written by openpyxl and odfpy (tools/build_spreadsheets.py), and a project laid out as Origin lays one out
  const F = A.files, bytesOf = (name) => new Uint8Array(fs.readFileSync(path.join(ROOT, 'tests/data', name)));
  const sheetsText = (tables) => tables.map((t) => { const r = A.importer.read(t.text, t.name); return t.name + ': ' + r.columns.map((c) => c.title + '[' + c.unit + ']=' + JSON.stringify(c.values)).join(' '); }).join(' ; ');
  const want = 'sample · Spectrum: Energy[eV]=[1.5,2.25,3,-4.5e-7] Counts[]=[10,null,1234567.891,0] Note[]=["start",null,"a b","end"] ; sample · Résistance: T[K]=[4.2,77,300] R[Ω]=[0.001,12.5,99.75]';
  const fromExcel = sheetsText(await F.read(bytesOf('sample.xlsx'), 'sample.xlsx')), fromCalc = sheetsText(await F.read(bytesOf('sample.ods'), 'sample.ods'));
  ok('a workbook of Excel and one of LibreOffice give the same sheets: names and units from the first line, an empty cell, a text among numbers, a sheet that starts at C3', fromExcel === want && fromCalc === want, fromExcel + ' /// ' + fromCalc);
  const refusal = async (bytes, name) => { try { await F.read(bytes, name); return ''; } catch (e) { return e.message; } };
  ok('what a file is, is read from its first bytes as much as from its name; what cannot be read says what to do', F.kind('a.xlsx') === 'xlsx' && F.kind('a.ODS') === 'ods' && F.kind('a.opj') === 'origin' && F.kind('notes.org', new TextEncoder().encode('* a text of Emacs')) === null
    && F.kind('data.csv') === null && F.kind('renamed.txt', bytesOf('sample.xlsx')) === null && F.kind('x.xlsx', new TextEncoder().encode('a,b\n1,2')) === null && F.kind('old.dat', new Uint8Array([0x43, 0x50, 0x59, 0x41, 0x20])) === 'origin'
    && /save it as \.xlsx/.test(await refusal(new Uint8Array([0xd0, 0xcf, 0x11, 0xe0, 0, 0, 0, 0, 0, 0]), 'old.xls')) && /Save Project As/.test(await refusal(new TextEncoder().encode('CPYUA 4.3 #\n....'), 'new.opju'))
    && /not a zip/.test(await refusal(new Uint8Array([0x50, 0x4b, 3, 4, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]), 'broken.xlsx')));
  // a project of Origin: a line that names the format, then blocks (a size on four bytes, a line feed, the bytes, a line feed); datasets, then windows whose layers hold the columns as curves
  const u32 = (v) => { const b = Buffer.alloc(4); b.writeUInt32LE(v); return b; }, nl = Buffer.from('\n'), zero = Buffer.concat([u32(0), nl]);
  const blockOf = (buf) => Buffer.concat([u32(buf.length), nl, buf, buf.length ? nl : Buffer.alloc(0)]);
  const MISSING = -1.23456789e-300;
  const dataset = (name, type, width, values, last) => {
    const hd = Buffer.alloc(0x7b), d = Buffer.alloc(values.length * width);
    hd.writeUInt16LE(type, 0x16); hd.writeInt32LE(values.length, 0x19); hd.writeInt32LE(last == null ? values.length : last, 0x21); hd[0x3d] = width; hd.write(name, 0x58, 'latin1');
    values.forEach((v, i) => { if (width === 8) d.writeDoubleLE(v, i * 8); else if (typeof v === 'number') d.writeDoubleLE(v, i * width + 2); else { d[i * width] = 1; d.write(v, i * width + 2, 'latin1'); } });
    return Buffer.concat([blockOf(hd), blockOf(d), zero]);
  };
  const curve = (id, role, name, label) => { const hd = Buffer.alloc(0x60); hd.writeUInt16LE(id, 0x04); hd[0x11] = role; hd.write(name, 0x12, 'latin1'); return Buffer.concat([blockOf(hd), blockOf(Buffer.from(label ? label + '\0' : '', 'latin1'))]); };
  const windowOf = (name, layers) => { const w = Buffer.alloc(0x40); w.write(name, 0x02, 'latin1'); return Buffer.concat([blockOf(w)].concat(layers.map((curves) => Buffer.concat([blockOf(Buffer.alloc(0x20, 1)), zero].concat(curves, [zero, zero, zero, zero, zero]))), [zero])); };
  const opjHead = Buffer.alloc(0x27); opjHead.writeDoubleLE(9.5, 0x1b);
  const project = Buffer.concat([Buffer.from('CPYA 4.3380 500#\n'), blockOf(opjHead), zero,
    dataset('Book1_A', 0x6001, 8, [1, 2, 3, 4, 0, 0], 4), dataset('Book1_B', 0x6001, 8, [10, MISSING, 30, 40, MISSING, MISSING]), dataset('Book1_C', 0x6121, 10, [0.5, 'bad', 0.7, 0.9]),
    dataset('Fit_Curve', 0x60b1, 8, [1e-310]), dataset('Book2_A', 0x6001, 8, [5, 6]), dataset('Book2_A@2', 0x6001, 8, [7, 8, 9]), dataset('Table1_A', 0x4121, 24, ['cell://Notes.Model', 'embedding:FitLine']), dataset('MBook1', 0x6001, 8, [1, 2, 3, 4]), zero,
    windowOf('Book1', [[curve(1, 3, 'A', 'Energy\r\neV\r\nmeasured@${x}'), curve(2, 0, 'B', 'Counts'), curve(3, 2, 'C', '')]]), windowOf('Graph1', [[curve(2, 0, 'B', '')]]), windowOf('Book2', [[curve(5, 3, 'A', '')], [curve(6, 3, 'A', 'Time\r\ns')]]), zero,
    Buffer.from('what follows is not read')]);
  const sheetsOf = (bytes) => F.origin(new Uint8Array(bytes)).map((t) => t.name + ': ' + t.read.columns.map((c) => c.role + ' ' + c.title + '[' + c.unit + ']=' + JSON.stringify(c.values)).join(' ') + (t.said.length ? ' !' : '')).join(' ; ');
  const cutShort = Buffer.concat([project.subarray(0, project.indexOf('Graph1') - 8)]);            // a file that ends in its windows: the values are there, the names are not
  ok('a project of Origin: the values of each worksheet, empty cells, a text among numbers, the long name, the unit and the role of each column; functions, matrices and tables of Origin’s own are left',
    sheetsOf(project) === 'Book1: x Energy[eV]=[1,2,3,4] y Counts[]=[10,null,30,40] yerr C[]=[0.5,"bad",0.7,0.9] ; Book2 · sheet 1: x A[]=[5,6] ; Book2 · sheet 2: x Time[s]=[7,8,9]'
    && (await F.read(new Uint8Array(project), 'run.opj')).map((t) => t.name).join() === 'run · Book1,run · Book2 · sheet 1,run · Book2 · sheet 2', sheetsOf(project));
  // its graphs: a window whose layers hold axes, texts and curves that name datasets by their number
  const layerOf = (x, y, rect) => { const l = Buffer.alloc(0x110); [x, y].forEach((ax, k) => { const at = k ? 0x3a : 0x0f; l.writeDoubleLE(ax[0], at); l.writeDoubleLE(ax[1], at + 8); l.writeDoubleLE(ax[2], at + 16); l[k ? 0x63 : 0x38] = ax[3]; }); rect.forEach((v, k) => l.writeInt16LE(v, 0x71 + 2 * k)); return blockOf(l); };
  const noteOf = (name, kind, attach, rect, d1, text, colour) => { const hd = Buffer.alloc(0x70); hd[0x02] = kind; rect.forEach((v, k) => hd.writeInt16LE(v, 0x03 + 2 * k)); hd[0x28] = attach; Buffer.from(colour || [0, 0, 0, 0]).copy(hd, 0x33); hd.write(name, 0x46, 'latin1');
    return Buffer.concat([blockOf(hd), blockOf(d1), blockOf(Buffer.from(text ? text + '\0' : '', 'latin1')), zero]); };
  const drawnAs = (yId, xId, type, more) => { const hd = Buffer.alloc(0x170); hd.writeUInt16LE(yId, 0x04); hd.writeUInt16LE(xId, 0x23); hd[0x4c] = type; more = more || {}; hd[0x11] = more.connect || 1; hd[0x12] = more.style || 0; hd.writeUInt16LE((more.width || 0.5) * 500, 0x15);
    hd[0x17] = more.shape || 2; hd[0x18] = more.interior || 0; hd.writeUInt16LE((more.size || 9) * 500, 0x19); Buffer.from(more.line || [0, 0, 0, 0]).copy(hd, 0x16a); Buffer.from(more.symbol || [0xf7, 0, 0, 0xff]).copy(hd, 0x132); return Buffer.concat([blockOf(hd), zero]); };
  const arrowTo = Buffer.alloc(0x78); arrowTo[0] = 2; arrowTo.writeDoubleLE(1, 0x20); arrowTo.writeDoubleLE(3, 0x28); arrowTo.writeDoubleLE(20, 0x40); arrowTo.writeDoubleLE(40, 0x48); arrowTo[0x6c] = 1;
  const plain66 = Buffer.alloc(0x66), box = [100, 100, 1100, 800];
  const graphWindow = (name, layers) => { const w = Buffer.alloc(0x60); w.write(name, 0x02, 'latin1'); w.write('LINE', 0x45, 'latin1'); return Buffer.concat([blockOf(w)].concat(layers.map((l) => Buffer.concat([l.head].concat(l.notes, [zero], l.curves, [zero, zero, zero, zero, zero]))), [zero])); };
  const withGraph = Buffer.concat([project.subarray(0, project.indexOf('what follows') - 5),
    graphWindow('Graph2', [
      { head: layerOf([0, 5, 1, 0], [1, 1000, 0, 1], box), notes: [noteOf('XB', 0, 0x22, [500, 820, 700, 860], plain66, '%(?X)'), noteOf('YL', 0, 0x22, [20, 300, 60, 600], plain66, '\\b(Counts) (s\\+(-1)), \\g(m) and \\f:Times New Roman(\\(x03C7))_raw'),
        noteOf('Legend', 0, 0x20, [850, 120, 1050, 220], plain66, '\\l(1) %(1)\r\n\\l(2) the fit'), noteOf('Text', 0, 0, [200, 150, 400, 220], plain66, 'T = 4 K\r\n\\i(sample) A_1', [1, 0, 0, 0]),
        noteOf('Line1', 0x22, 2, [0, 0, 10, 10], arrowTo, '', [0x10, 0x20, 0x30, 1]), noteOf('__LayerInfoStorage', 35, 0, [0, 0, 0, 0], Buffer.alloc(0x40), '@${opaque}')],
        curves: [drawnAs(2, 1, 201, { shape: 1, symbol: [1, 0, 0, 0] }), drawnAs(3, 1, 231), drawnAs(2, 1, 200, { style: 1, width: 1.5, line: [0x10, 0x20, 0x30, 1] }), drawnAs(2, 1, 226)] },
      { head: layerOf([0, 5, 1, 0], [9, 2, 1, 0], box), notes: [noteOf('YR', 0, 0x22, [1120, 300, 1160, 600], plain66, 'Other')], curves: [drawnAs(5, 0, 202, { connect: 11 })] }]),
    graphWindow('Graph3', [{ head: layerOf([0, 1, 1, 0], [0, 1, 1, 0], box), notes: [], curves: [drawnAs(1, 0, 219)] }]), zero]);
  const read2 = F.origin(new Uint8Array(withGraph)), spec = read2.graphs[0], p0 = spec ? spec.panels[0] : null;
  ok('a graph of an Origin project: a panel for a layer, a layer laid over it as its right axis; ranges and scales; the titles in the markup of this page; a legend, a text, an arrow; an error column joined to its curve',
    read2.graphs.length === 1 && spec.name === 'Graph2' && spec.panels.length === 1 && JSON.stringify(p0.x) === '{"label":"Energy (eV)","scale":"linear","min":0,"max":5,"step":1,"reverse":false}'
    && JSON.stringify(p0.y) === '{"label":"Counts (s^{-1}), \\\\mu{} and χ\\\\_raw","scale":"log","min":1,"max":1000,"step":null,"reverse":false}' && JSON.stringify(p0.y2) === '{"label":"Other","scale":"linear","min":2,"max":9,"step":1,"reverse":true}'
    && p0.curves.map((c) => [c.table, c.x, c.y, c.yerr, c.axis, c.type, c.color, c.dash, c.marker, c.width, c.label].join(',')).join(' ; ') === 'Book1@1,0,1,2,y,scatter,#ff0000,solid,square,0.5, ; Book1@1,0,1,,y,line,#102030,dash,circle,1.5,the fit ; Book2@1,,0,,y2,both,#000000,solid,circle,0.5,'
    && JSON.stringify(p0.legend) === '{"x":0.75,"y":0.0286}' && p0.notes.map((n) => n.type + ':' + (n.text || [n.coords, n.x, n.y, n.x2, n.y2, n.color].join())).join(' ; ') === 'text:T = 4 K\nsample A\\_1 ; arrow:data,1,20,3,40,#102030' && p0.notes[0].color === '#ff0000'
    && /a contour plot/.test(spec.said.join()) && /a histogram/.test(read2.left.join()) && read2.length === 3,
    spec ? JSON.stringify(p0.x) + ' ' + JSON.stringify(p0.y) + ' ' + JSON.stringify(p0.y2) + ' // ' + p0.curves.map((c) => [c.table, c.x, c.y, c.yerr, c.axis, c.type, c.color, c.dash, c.marker, c.width, c.label].join(',')).join(' ; ') + ' // ' + JSON.stringify(p0.legend) + ' // ' + JSON.stringify(p0.notes) + ' // ' + spec.said.join() + ' // ' + read2.left.join() : 'no graph');
  M.blank('From Origin');
  const sheetsMade = {}; read2.forEach((t, k) => { if (k !== 1) sheetsMade[t.key] = M.sheetFrom(t.name, t.read.columns, ''); });          // one of its sheets is left out: its curve is too
  const gMade = M.graphFrom(spec, (key) => sheetsMade[key] || null), pm = gMade.figure.panels[0], book1 = sheetsMade['Book1@1'];
  ok('made here: the curves name the columns of the sheets that were imported, a curve of a sheet that was left out is left; the axes, the legend in the nearest corner, the texts and the arrows are those of the graph',
    gMade.name === 'Graph2' && pm.series.length === 2 && pm.series[0].sheet === book1.id && pm.series[0].x === book1.columns[0].id && pm.series[0].y === book1.columns[1].id && pm.series[0].yerr === book1.columns[2].id && pm.series[0].type === 'scatter'
    && pm.series[1].label === 'the fit' && pm.series[1].dash === 'dash' && pm.series[1].width === 1.5 && pm.y.scale === 'log' && pm.y.min === 1 && pm.x.label === 'Energy (eV)' && pm.y2 && pm.y2.reverse === true && pm.legend.pos === 'ne'
    && pm.notes.length === 2 && pm.notes[0].type === 'text' && pm.notes[1].type === 'arrow' && pm.notes[1].coords === 'data' && gMade.figure.height === Math.round(120 * 0.7)
    && P.layout(gMade.figure, M.seriesData).items.some((it) => it.t === 'text' && it.k === 'ylabel:' + pm.id && it.runs.map((r) => r.s).join('|') === 'Counts (s|−1|), μ and χ_raw')
    && M.graphFrom({ name: 'Nothing', panels: [{ x: {}, y: {}, curves: [{ table: 'gone', x: 0, y: 1 }] }] }, () => null) === null && M.doc.graphs.length === 1);
  // functions drawn on a graph ("Add Function Graph"), and texts with their colour, their size, their turn and the place Origin keeps for them
  const functionOf = (name, formula, points, begin, step) => { const hd = Buffer.alloc(0x8c); hd.writeUInt16LE(0x6081, 0x16); hd.writeInt32LE(points, 0x21); hd.writeDoubleLE(begin, 0x25); hd.writeDoubleLE(step, 0x2d); hd[0x3d] = 100; hd.write(name, 0x58, 'latin1');
    return Buffer.concat([blockOf(hd), blockOf(Buffer.from(formula + '\0', 'latin1')), zero]); };
  const textAt = (name, px, py, text, more) => { more = more || {}; const hd = Buffer.alloc(0x70), d1 = Buffer.alloc(62); hd.writeDoubleLE(px, 0x13); hd.writeDoubleLE(py, 0x1b); hd[0x28] = more.attach || 0; hd.write(name, 0x46, 'latin1');
    [more.left || 300, more.top || 300, 400, 340].forEach((v, k) => hd.writeInt16LE(v, 0x03 + 2 * k)); d1.writeInt16LE((more.turn || 0) * 10, 0x02); d1[4] = more.font || 22; d1[8] = more.centred ? 0x26 : 0;
    return Buffer.concat([blockOf(hd), blockOf(d1), blockOf(Buffer.from(text + '\0', 'latin1')), zero]); };
  const pageWindow = (name, layers) => { const w = Buffer.alloc(0x60); w.write(name, 0x02, 'latin1'); w.writeUInt16LE(1300, 0x23); w.writeUInt16LE(1000, 0x25); w.write('LINE', 0x45, 'latin1'); return Buffer.concat([blockOf(w)].concat(layers.map((l) => Buffer.concat([l.head].concat(l.notes, [zero], l.curves, [zero, zero, zero, zero, zero]))), [zero])); };
  const drawnProject = Buffer.concat([Buffer.from('CPYA 4.2878 724#\n'), blockOf(opjHead), zero,
    dataset('Run_A', 0x6001, 8, [0, 1, 2, 3]), dataset('Run_B', 0x6001, 8, [1, 3, 5, 8]), functionOf('F1', '2*x+1', 5, 0, 1), functionOf('F2', '6.5', 5, 0, 1), functionOf('F3', 'Exp(-x/7.5)', 3, 10, 5), functionOf('F4', 'besselj(x)', 5, 0, 1), functionOf('F5', '9', 5, 0, 1), zero,
    windowOf('Run', [[curve(1, 3, 'A', ''), curve(2, 0, 'B', '')]]),
    pageWindow('Graph1', [{ head: layerOf([0, 4, 1, 0], [0, 10, 2, 0], box), notes: [textAt('XB', 2, 0, 'Time (min)', { attach: 0x22, centred: true }), textAt('Text1', 0.5, 0.25, '\\p69(400°C)\r\n\\p69(under)', { centred: true }),
      textAt('Text2', 0.1, 0.4, '\\p69(300°C)', { turn: 90 }), textAt('Text3', 0.2, 0.1, '\\g(\\p144(\\c17(t =)))\\c17( 7.5 min)', { font: 18 }), textAt('Text4', 0.3, 0.2, '\\c16809985(late)'), textAt('Text5', 0.8, -0.44, 'an older copy', { top: -400 }),
      textAt('Text6', 3, 7, 'on the scales', { attach: 2 })],
      curves: [drawnAs(2, 1, 201), drawnAs(3, 0, 200, { line: [1, 0, 0, 0] }), drawnAs(4, 0, 200, { style: 2, line: [19, 0, 0, 0] }), drawnAs(5, 0, 200), drawnAs(6, 0, 200)] }]), zero]);
  const read3 = F.origin(new Uint8Array(drawnProject)), fnTable = read3.find((t) => t.key === 'functions'), p3 = read3.graphs[0].panels[0];
  ok('the functions drawn on a graph of Origin become a sheet: a column of x for each grid, and each function with its formula and its values; what this page cannot compute is left empty and said; a function no graph draws is left',
    read3.length === 2 && fnTable.read.columns.map((c) => c.title + (c.fx ? '=' + c.fx + '@' + c.on : '') + ':' + JSON.stringify(c.values)).join(' ; ') === 'x:[0,1,2,3,4] ; F1=2*x+1@0:[1,3,5,7,9] ; F2=6.5@0:[6.5,6.5,6.5,6.5,6.5] ; F4:[null,null,null,null,null] ; x:[10,15,20] ; F3=exp(-x/7.5)@4:' + JSON.stringify([10, 15, 20].map((x) => Math.exp(-x / 7.5)))
    && /F4 is not one this page computes/.test(read3[0].said.join()) && p3.curves.map((c) => [c.table, c.x, c.y, c.type, c.color, c.dash, c.label].join(',')).join(' ; ') === 'Run@1,0,1,scatter,#000000,solid, ; functions,,1,line,#ff0000,solid,2*x+1 ; functions,,2,line,#808080,dot,6.5 ; functions,,5,line,#000000,solid,Exp(-x/7.5) ; functions,,3,line,#000000,solid,besselj(x)',
    fnTable ? fnTable.read.columns.map((c) => c.title + (c.fx ? '=' + c.fx + '@' + c.on : '') + ':' + JSON.stringify(c.values)).join(' ; ') + ' // ' + p3.curves.map((c) => [c.table, c.x, c.y, c.type, c.color, c.dash, c.label].join(',')).join(' ; ') + ' // ' + read3[0].said.join() : 'no table of functions');
  ok('a text of Origin stands where the file says: by its top left corner, or by its centre when it is centred, on the frame or on the scales; with its colour, its size beside that of the titles, its turn; one left outside the page is not taken',
    p3.x.label === 'Time (min)' && p3.notes.map((n) => [n.text.replace(/\n/g, '/'), n.coords, n.x, n.y, n.anchor, n.valign, n.color, n.scale, n.rotate].join(',')).join(' ; ')
      === '400°C/under,axes,0.5,0.75,middle,middle,#000000,0.69,0 ; 300°C,axes,0.1,0.6,start,top,#000000,0.69,90 ; \\tau{} = 7.5 min,axes,0.2,0.9,start,top,#ff0080,0.82,0 ; late,axes,0.3,0.8,start,top,#018000,1,0 ; on the scales,data,3,7,start,top,#000000,1,0'
    && F.originScale('\\p144(\\c17(\\p83(6.56)))') === 1.44 * 0.83 && F.originColour('\\c2(a-CdS)') === '#ff0000' && F.originColour('plain') === null,
    p3.notes.map((n) => [n.text.replace(/\n/g, '/'), n.coords, n.x, n.y, n.anchor, n.valign, n.color, n.scale, n.rotate].join(',')).join(' ; '));
  M.blank('Functions');
  const made3 = {}; read3.forEach((t) => { made3[t.key] = M.sheetFrom(t.name, t.read.columns, ''); });
  const fs3 = made3.functions, g3 = M.graphFrom(read3.graphs[0], (key) => made3[key] || null), pn = g3.figure.panels[0];
  const laid3 = P.layout(g3.figure, M.seriesData), texts3 = (n) => laid3.items.filter((it) => it.t === 'text' && it.k === 'note:' + n.id);
  fs3.columns[0].values[1] = 10; M.changed(fs3);
  ok('made here: a function is a column that keeps its formula on its column of x and follows it; its curve is drawn on them; a centred text is laid about its centre, a turned one is turned, one outside the frame has its room on the page',
    fs3.columns.map((c) => c.name + (c.formula ? '=' + c.formula : '')).join() === 'A,B=2*A+1,C=6.5,D,E,F=exp(-E/7.5)' && fs3.columns[1].values.join() === '1,21,5,7,9' && pn.series.length === 5 && pn.series[1].x === fs3.columns[0].id && pn.series[1].y === fs3.columns[1].id
    && pn.series[3].x === fs3.columns[4].id && pn.series[1].label === '2*x+1' && pn.notes.length === 5 && pn.notes[0].size === Number((9 * 0.69).toFixed(1)) && texts3(pn.notes[0]).length === 2 && texts3(pn.notes[0]).every((it) => it.anchor === 'middle')
    && Math.abs((texts3(pn.notes[0])[0].y + texts3(pn.notes[0])[1].y) / 2 - pn.notes[0].size * 0.35 - (laid3.hit.panels[0].box.y + 0.25 * laid3.hit.panels[0].box.h)) < 0.02 && texts3(pn.notes[1])[0].rotate === -90
    && (() => { const far = JSON.parse(JSON.stringify(g3.figure)); far.panels[0].notes.push({ id: 'nx', type: 'text', coords: 'axes', x: 1.05, y: 0.5, text: 'outside, on the right', size: 9 }, { id: 'ny', type: 'text', coords: 'axes', x: -0.2, y: 1.15, text: 'M3799', size: 9, valign: 'top' });
      const l = P.layout(far, M.seriesData), b = l.hit.panels[0].box, b0 = laid3.hit.panels[0].box, right = l.items.find((it) => it.k === 'note:nx'), top = l.items.find((it) => it.k === 'note:ny');
      return b.w < b0.w - 60 && right.x + P.textWidth('outside, on the right', 9) <= l.width * P.MM + 0.5 && top.x >= 0 && top.y - 9 >= 0 && b.y > b0.y + 10; })(),
    fs3.columns.map((c) => c.name + (c.formula ? '=' + c.formula : '')).join() + ' / ' + fs3.columns[1].values.join() + ' / ' + pn.series.length + ' / ' + pn.notes.length + ' / ' + (pn.notes[0] ? pn.notes[0].size : ''));
  let ended = ''; try { F.origin(new Uint8Array(project.subarray(0, 300))); } catch (e) { ended = e.message; }
  ok('a project that ends too early says so; one whose windows stop being readable still gives every value, the names it read, and says that some are missing', /ends before its data/.test(ended) && /^Book1: x Energy\[eV\]=\[1,2,3,4\] /.test(sheetsOf(cutShort)) && /Book2 · sheet 2: x A\[\]=\[7,8,9\] !$/.test(sheetsOf(cutShort)), ended + ' /// ' + sheetsOf(cutShort));
  console.log(failed ? '\n' + failed + ' FAILED' : '\nall ok');
  process.exit(failed ? 1 : 0);
})();
