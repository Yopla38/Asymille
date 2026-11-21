#!/usr/bin/env node
/* The parts of the page that hold logic and no DOM, run in Node:
 *
 *     node tools/check_page.js            prints ok / FAILED per line, exits 1 on a failure
 *     node tools/check_page.js --write    also writes tests/data/project.json, which tests/test_api.py posts to the API
 *
 *   1  formulas (expr.js) give the values asymille/expressions.py gives for the same text (tests/data/expressions.json)
 *   2  the importer reads the example files, a European CSV, a file with a heading
 *   3  the project (model.js): formulas, sorting, undo; serialize and restore are exact inverses
 *   4  a figure (plot.js): ticks, markup, and a layout whose every number is finite and inside the page
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
graph.figure.panels[0].y2 = P.axis({ label: 'Second (\\mu{}V)' });
graph.figure.panels[0].notes.push({ id: M.id('n'), type: 'text', x: 2, y: 30, text: 'T = 4 K', size: 8, coords: 'data' }, { id: M.id('n'), type: 'span', x: 1.5, x2: 2.5, color: '#e69f00', opacity: 0.2 });
M.log('Checked.'); M.doc.log.forEach((l) => { l.at = '2026-01-01T00:00:00.000Z'; });        // the same project at every run
M.commit();
const data = M.seriesData;
ok('a series of data reads its columns, with NaN where a cell is text', (() => { const d = data(graph.figure.panels[0].series.find((r) => r.kind === 'data')); return d.x.length === 4 && isNaN(d.y[1]) && d.yerr[3] === 2 && d.label === 'Counts'; })());
ok('the curves of a fit are series of the graph: total, band, components, residuals in a panel below', graph.figure.panels.length === 2 && graph.figure.panels[0].series.length === 5 && data(graph.figure.panels[1].series[0]).y.length === 3 && graph.figure.layout.shareX === true);
const written = JSON.stringify(M.serialize());
M.restore(JSON.parse(written));
ok('a project written and read back is the same project', JSON.stringify(M.serialize()) === written);
ok('what is sent to be fitted: null where a cell is not a number', JSON.stringify(M.fitData(M.fit(fit.id))) === '{"x":[1,2,3,4],"y":[10,null,30,40],"sigma":[1,1,1,2]}');
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
const empty = P.layout(Object.assign(P.defaults(), { panels: [Object.assign(P.panel('p1'), { y: P.axis({ scale: 'log' }), series: [P.series({ id: 'r1' })] })] }), () => ({ x: [1, 2], y: [-1, -2] }));
ok('a logarithmic axis with no positive value is said, not drawn empty in silence', empty.hit.warnings.length === 1 && /none of its values is positive/.test(empty.hit.warnings[0]));
const long = Array.from({ length: 50000 }, (_, i) => i), dense = P.layout(Object.assign(P.defaults(), { panels: [Object.assign(P.panel('p1'), { series: [P.series({ id: 'r1', type: 'line' })] })] }), () => ({ x: long, y: long.map((v) => Math.sin(v / 50)) }));
const drawn = dense.items.find((it) => it.t === 'line' && it.k === 'series:r1').paths[0].length / 2;
ok('a curve of 50 000 points is drawn with ' + drawn + ': what a page can show', drawn < 8000 && drawn > 1000);

console.log(failed ? '\n' + failed + ' FAILED' : '\nall ok');
process.exit(failed ? 1 : 0);
