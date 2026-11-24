"""A figure drawn into a file: its true size, its font embedded, and what is refused."""
from __future__ import annotations

import io
import json
import re
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from asymille import figures
from asymille.figures import FigureError, render

ROOT = Path(__file__).resolve().parent.parent
FIGURE = {"width": 89, "height": 64, "font": "Arial", "background": "#ffffff", "items": [
    {"t": "poly", "pts": [0, 0, 252.28, 0, 252.28, 181.42, 0, 181.42], "fill": "#ffffff"},
    {"t": "line", "paths": [[30, 20, 220, 20, 220, 160, 30, 160, 30, 20]], "stroke": "#000000", "width": 0.5},
    {"t": "poly", "pts": [40, 150, 100, 60, 160, 150], "fill": "#0072b2", "opacity": 0.2, "clip": [30, 20, 190, 140]},
    {"t": "line", "paths": [[30, 150, 100, 40, 240, 150]], "stroke": "#d55e00", "width": 1, "dash": [4, 2], "clip": [30, 20, 190, 140]},
    {"t": "marks", "pts": [50, 100, 80, 90], "size": 4, "circle": True, "fill": "#ffffff", "stroke": "#0072b2", "width": 0.6},
    {"t": "marks", "pts": [50, 120], "size": 4, "verts": [[0, -0.5], [0.5, 0.5], [-0.5, 0.5]], "fill": "#009e73", "stroke": None},
    {"t": "marks", "pts": [150, 120], "size": 4, "strokes": [[-0.5, -0.5, 0.5, 0.5], [-0.5, 0.5, 0.5, -0.5]], "stroke": "#000000", "width": 0.6},
    {"t": "text", "x": 125, "y": 175, "runs": [{"s": "E − E"}, {"s": "F", "v": -1}, {"s": " (eV), 10"}, {"s": "−3", "v": 1}], "size": 8, "anchor": "middle"},
    {"t": "text", "x": 12, "y": 90, "runs": [{"s": "50 % of $x_1 {a} \\b & c # ~ α"}], "size": 8, "anchor": "middle", "rotate": -90, "weight": "bold"},
]}


def test_a_pdf_has_the_size_asked_and_holds_its_font() -> None:
    made = render(FIGURE, "pdf")
    box = re.search(rb"/MediaBox \[ 0 0 ([\d.]+) ([\d.]+) \]", made.data)
    assert box and float(box.group(1)) == pytest.approx(89 * 72 / 25.4, abs=0.01) and float(box.group(2)) == pytest.approx(64 * 72 / 25.4, abs=0.01)
    assert made.data.startswith(b"%PDF") and b"/FontFile2" in made.data and b"/Type3" not in made.data       # TrueType, embedded: text stays text
    assert made.font.encode().replace(b" ", b"") in made.data and (made.width, made.height) == (89, 64)
    assert render(FIGURE, "pdf").data == made.data                                                           # the same figure, the same file
    if made.font != "Arial":
        assert made.notes and "Arial is not installed" in made.notes[0]


@pytest.mark.parametrize("fmt, dpi", [("png", 300), ("tiff", 600)])
def test_pixels_at_the_resolution_asked(fmt: str, dpi: int) -> None:
    image = Image.open(io.BytesIO(render(FIGURE, fmt, dpi).data))
    assert image.size[0] == pytest.approx(89 / 25.4 * dpi, abs=1) and image.size[1] == pytest.approx(64 / 25.4 * dpi, abs=1) and round(float(image.info["dpi"][0])) == dpi
    if fmt == "tiff":
        assert image.info["compression"] == "tiff_lzw"
    assert image.convert("RGB").getpixel((5, 5)) == (255, 255, 255)
    reds = [image.convert("RGB").getpixel((round(100 / 252.28 * image.size[0]), y))[0] for y in range(image.size[1])]
    assert min(reds) < 255                                                                                    # something was drawn


def test_eps_says_that_transparency_was_flattened() -> None:
    made = render(FIGURE, "eps")
    assert made.data.startswith(b"%!PS-Adobe") and any("EPS has no transparency" in n for n in made.notes)
    opaque = dict(FIGURE, items=[i for i in FIGURE["items"] if "opacity" not in i])
    assert not any("transparency" in n for n in render(opaque, "eps").notes)


def test_the_page_and_the_server_draw_the_same_list(tmp_path: Path) -> None:
    """A figure laid out by page/js/plot.js is drawn here without a complaint: the two ends of one list."""
    script = """
    global.window = {}; for (const f of ['util', 'expr', 'importer', 'plot', 'model']) require('./page/js/' + f + '.js');
    const A = window.ASY, M = A.model; A.fnLabel = (c) => c.fn;
    M.restore(JSON.parse(require('fs').readFileSync('tests/data/project.json', 'utf8')));
    process.stdout.write(JSON.stringify(A.plot.sendable(A.plot.layout(M.doc.graphs[0].figure, M.seriesData))));
    """
    try:
        listed = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=60, check=True).stdout
    except FileNotFoundError:
        pytest.skip("node is not installed")
    figure = json.loads(listed)
    assert len(figure["items"]) > 25 and {i["t"] for i in figure["items"]} == {"poly", "line", "marks", "text"}
    for fmt in ("pdf", "eps", "png"):
        assert len(render(figure, fmt, 150).data) > 3000


@pytest.mark.parametrize("change, said", [
    (lambda f: f.update(items="none"), "no list of things to draw"), (lambda f: f.update(width=9000), "the width"),
    (lambda f: f["items"].append({"t": "line", "paths": [[1, 2, 3, float("nan")]], "stroke": "#000000"}), "not a number"),
    (lambda f: f["items"].append({"t": "line", "paths": [[1, 2, 3]], "stroke": "#000000"}), "x, y pairs"),
    (lambda f: f["items"].append({"t": "poly", "pts": [1, 2, 3, 4, 5, 6], "fill": "red; drop"}), "not a colour"),
    (lambda f: f["items"].append({"t": "image", "href": "file:///etc/passwd"}), "is not something this can draw"),
    (lambda f: f["items"].append({"t": "text", "x": 1, "y": 1, "runs": "abc"}), "a list of runs"),
    (lambda f: f.update(items=[{"t": "poly", "pts": [0, 0, 1, 1, 2, 2], "fill": "#000000"}] * 50001), "50000 things"),
])
def test_what_is_not_a_figure_is_refused(change, said: str) -> None:
    figure = json.loads(json.dumps(FIGURE))
    change(figure)
    with pytest.raises(FigureError, match=said):
        render(figure, "pdf")
    with pytest.raises(FigureError, match="20 000 pixels"):
        render(dict(FIGURE, width=900, height=600), "tiff", 1200)


def test_the_fonts_the_server_can_stand_in() -> None:
    listed = {f["name"]: f for f in figures.fonts()}
    assert set(listed) == {"Arial", "Helvetica", "Times New Roman", "DejaVu Sans"} and listed["DejaVu Sans"]["used"] == "DejaVu Sans" and not listed["DejaVu Sans"]["note"]
    assert all(f["used"] != f["name"] or not f["note"] for f in listed.values())
