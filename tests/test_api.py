"""The API: projects that belong to their owner, computing behind it, and what it refuses."""
from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import DateTime, Integer, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from asymille.web import Host, Limits, build
from asymille.web.standalone import create_app

DATA = Path(__file__).resolve().parent / "data"
PROJECT = json.loads((DATA / "project.json").read_text())          # written by tools/check_page.js from page/js/model.js
ORIGIN = "http://testserver"


class Page:
    """What the page does: ask for the token, send it back with the Origin."""

    def __init__(self, app: FastAPI, **headers: str) -> None:
        self.http = TestClient(app, base_url=ORIGIN)
        self.headers = headers
        self.token = self.http.get("/api/auth/me").json().get("csrf", "") if not headers else ""

    def get(self, path: str) -> Any:
        return self.http.get("/api/asymille" + path, headers=self.headers)

    def send(self, method: str, path: str, body: Any = None) -> Any:
        return self.http.request(method, "/api/asymille" + path, json=body, headers={"Origin": ORIGIN, "X-CSRF-Token": self.token, **self.headers})

    def post(self, path: str, body: Any = None) -> Any:
        return self.send("POST", path, body)


@pytest.fixture()
def page() -> Page:
    return Page(create_app(":memory:", limits=Limits(max_projects=3)))


def test_the_catalogue_is_what_the_page_draws_its_lists_from(page: Page) -> None:
    cat = page.get("/catalogue").json()
    assert len(cat["functions"]) == 56 and len(cat["operations"]) == 18 and cat["families"][-1] == "Instrument response" and len(cat["journals"]["presets"]) == 28
    gaussian = next(f for f in cat["functions"] if f["name"] == "gaussian")
    assert gaussian["family"] == "Peaks" and [p["name"] for p in gaussian["params"]] == ["amplitude", "center", "sigma"] and gaussian["tex"].startswith("y = ")
    nature = next(p for p in cat["journals"]["presets"] if p["id"] == "nature-1")
    assert (nature["width"], nature["label"], nature["label_size"], nature["tick_size"], nature["font"]) == (89, "single column", 7, 6, "Arial")
    assert cat["limits"]["document_bytes"] is None                              # the standalone server has no limit; a host says its own
    assert {"leastsq", "differential_evolution"} <= set(cat["methods"]) and cat["fonts"][0]["name"] == "Arial" and "pdf" in cat["formats"]


def test_a_project_written_by_the_page_is_kept_as_it_is(page: Page) -> None:
    made = page.post("/projects", {"document": PROJECT})
    assert made.status_code == 201, made.text
    project = made.json()
    assert project["document"] == PROJECT                                      # nothing added, nothing lost: an empty cell stays null
    assert (project["name"], project["sheet_count"], project["graph_count"], project["fit_count"], project["revision"]) == ("Check", 4, 2, 1, 1)
    assert [p["id"] for p in page.get("/projects").json()] == [project["id"]]
    series = project["document"]["series"][0]                                  # the same fit on two files, with what the second gave, and the sheet of results
    assert series["variable"] == {"name": "Temperature", "unit": "K"} and [m["value"] for m in series["members"]] == [160, 180] and series["members"][1]["result"]["params"][0]["name"] == "p1_center"
    made = [c["made"] for s in project["document"]["sheets"] if s["id"] == series["results"] for c in s["columns"]]
    assert made[0] == {"series": series["id"], "key": "variable"} and {"series": series["id"], "key": "p1_center:err"} in made
    changed = dict(PROJECT, name="Renamed")
    saved = page.send("PUT", f"/projects/{project['id']}", {"document": changed, "revision": 1})
    assert saved.status_code == 200 and saved.json()["revision"] == 2 and saved.json()["name"] == "Renamed"
    stale = page.send("PUT", f"/projects/{project['id']}", {"document": PROJECT, "revision": 1})           # another tab, still at revision 1
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_revision"
    assert page.get(f"/projects/{project['id']}").json()["document"]["name"] == "Renamed"
    copy = page.post(f"/projects/{project['id']}/duplicate")
    assert copy.status_code == 201 and copy.json()["name"] == "Renamed (copy)" and copy.json()["document"]["sheets"] == PROJECT["sheets"]
    assert page.send("DELETE", f"/projects/{project['id']}").status_code == 204
    assert page.get(f"/projects/{project['id']}").status_code == 404 and len(page.get("/projects").json()) == 1


@pytest.mark.parametrize("change, said", [
    (lambda d: d.update(colour="red"), "colour"), (lambda d: d.update(version=2), "version"), (lambda d: d["sheets"][0].update(script="x"), "script"),
    (lambda d: d["sheets"][0]["columns"][0].update(id="Not An Id"), "id"), (lambda d: d["sheets"].append(dict(d["sheets"][0])), "same id"),
    (lambda d: d["sheets"][0]["columns"][0].update(values=[{"a": 1}]), "values"), (lambda d: d["fits"][0].update(mode="magic"), "mode"),
    (lambda d: d["series"][0]["members"][0].update(state="exploded"), "state"), (lambda d: d["series"][0].update(run="rm -rf"), "run"),
    (lambda d: d["series"].append(dict(d["series"][0])), "same id"),
])
def test_what_is_not_a_project_is_refused_with_the_name_of_what_is_wrong(page: Page, change: Any, said: str) -> None:
    document = json.loads(json.dumps(PROJECT))
    change(document)
    answer = page.post("/projects", {"document": document})
    assert answer.status_code == 422 and said in answer.json()["error"]["message"] + json.dumps(answer.json()["error"].get("fields", {}))


def test_a_project_saved_before_there_were_series_is_still_a_project(page: Page) -> None:
    old = json.loads(json.dumps(PROJECT))
    del old["series"]
    for sheet in old["sheets"]:
        for column in sheet["columns"]:
            del column["made"]
    made = page.post("/projects", {"document": old})
    assert made.status_code == 201 and made.json()["document"]["series"] == [] and made.json()["document"]["sheets"][0]["columns"][0]["made"] is None


def test_an_account_holds_so_many_projects(page: Page) -> None:
    for _ in range(3):
        assert page.post("/projects", {"document": PROJECT}).status_code == 201
    full = page.post("/projects", {"document": PROJECT})
    assert full.status_code == 409 and full.json()["error"]["code"] == "too_many_projects"
    first = page.get("/projects").json()[0]["id"]
    assert page.post(f"/projects/{first}/duplicate").status_code == 409


def test_a_request_that_changes_something_must_be_the_pages_own(page: Page) -> None:
    body = {"document": PROJECT}
    assert page.http.post("/api/asymille/projects", json=body).status_code == 403                                                    # no Origin: not a page of this server
    assert page.http.post("/api/asymille/projects", json=body, headers={"Origin": "http://evil.example", "X-CSRF-Token": page.token}).json()["error"]["code"] == "bad_origin"
    assert page.http.post("/api/asymille/projects", json=body, headers={"Origin": ORIGIN, "X-CSRF-Token": "guess"}).json()["error"]["code"] == "bad_csrf"
    form = page.http.post("/api/asymille/projects", content="document=1", headers={"Origin": ORIGIN, "X-CSRF-Token": page.token, "Content-Type": "application/x-www-form-urlencoded"})
    assert form.status_code == 415
    assert page.get("/projects").json() == []


# ── a host with accounts: what belongs to one does not exist for another ─────
def hosted() -> FastAPI:
    class Base(DeclarativeBase):
        pass

    class User(Base):
        __tablename__ = "users"
        id: Mapped[int] = mapped_column(Integer, primary_key=True)

    class Refused(Exception):
        def __init__(self, status: int, code: str, message: str) -> None:
            self.status, self.code, self.message = status, code, message

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    make = sessionmaker(bind=engine, expire_on_commit=False)

    def db() -> Iterator[Session]:
        with make() as session:
            yield session

    def user_id(x_user: int = Header()) -> int:              # the stand-in for a session: the host says who is signed in
        return x_user

    router = build(Host(base=Base, users="users.id", moment=DateTime(timezone=True), db=db, user_id=user_id, error=Refused))
    Base.metadata.create_all(engine)
    with make() as session:
        session.add_all([User(id=1), User(id=2)])
        session.commit()
    app = FastAPI()
    app.include_router(router, prefix="/api", dependencies=[Depends(lambda: None)])
    app.state.make, app.state.User = make, User

    @app.exception_handler(Refused)
    async def _refused(request: Request, exc: Refused) -> JSONResponse:
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)

    return app


def test_a_project_of_someone_else_does_not_exist() -> None:
    app = hosted()
    alice, bob = Page(app, **{"X-User": "1"}), Page(app, **{"X-User": "2"})
    mine = alice.post("/projects", {"document": PROJECT}).json()["id"]
    assert bob.get("/projects").json() == []
    assert bob.get(f"/projects/{mine}").status_code == 404
    assert bob.send("PUT", f"/projects/{mine}", {"document": PROJECT, "revision": 1}).status_code == 404
    assert bob.post(f"/projects/{mine}/duplicate").status_code == 404
    assert bob.send("DELETE", f"/projects/{mine}").status_code == 404
    assert alice.get(f"/projects/{mine}").json()["revision"] == 1               # untouched
    kept = alice.send("PUT", "/formats", {"name": "Thesis", "format": FORMAT}).json()["id"]            # the same holds for a format a person kept
    assert bob.get("/formats").json() == [] and bob.send("DELETE", f"/formats/{kept}").status_code == 404
    assert bob.send("PUT", "/formats", {"name": "Thesis", "format": {"width": 60}}).status_code == 200            # the same name, each their own
    assert alice.get("/formats").json()[0]["format"] == FORMAT
    with app.state.make() as session:                                         # an account that leaves takes its projects and its formats with it
        session.delete(session.get(app.state.User, 1))
        session.commit()
    assert alice.get("/projects").json() == [] and alice.get("/formats").json() == [] and len(bob.get("/formats").json()) == 1


FORMAT = {"width": 86, "height": 64, "font": "Helvetica", "background": "#ffffff", "journal": None, "palette": "okabe", "size": {"label": 8, "tick": 7, "legend": 7, "title": 8, "tag": 9},
          "stroke": {"axis": 0.5, "line": 1, "grid": 0.35, "error": 0.5}, "tick": {"dir": "in", "len": 3, "mirror": True}, "frame": "box"}


def test_a_format_is_kept_under_a_name_and_replaced_by_one_of_the_same_name() -> None:
    page = Page(create_app(":memory:", limits=Limits(max_formats=2)))
    assert page.get("/formats").json() == [] and page.get("/catalogue").json()["limits"]["formats"] == 2
    first = page.send("PUT", "/formats", {"name": "  PRB single column ", "format": FORMAT})
    assert first.status_code == 200 and first.json()["name"] == "PRB single column" and first.json()["format"] == FORMAT          # kept as it was sent: a null stays a null
    again = page.send("PUT", "/formats", {"name": "PRB single column", "format": dict(FORMAT, width=90)})
    assert again.json()["id"] == first.json()["id"] and again.json()["format"]["width"] == 90
    assert page.send("PUT", "/formats", {"name": "A slide", "format": {"width": 250}}).status_code == 200
    assert [f["name"] for f in page.get("/formats").json()] == ["A slide", "PRB single column"]
    full = page.send("PUT", "/formats", {"name": "One more", "format": {}})
    assert full.status_code == 409 and full.json()["error"]["code"] == "too_many_formats"
    assert page.send("DELETE", f"/formats/{first.json()['id']}").status_code == 204 and page.send("DELETE", f"/formats/{first.json()['id']}").status_code == 404
    assert page.send("PUT", "/formats", {"name": "One more", "format": {}}).status_code == 200
    for bad in ({"name": "", "format": {}}, {"name": "x" * 61, "format": {}}, {"name": "x", "format": {"blob": "y" * 9000}}, {"name": "x", "format": {}, "owner_id": 2}, {"name": "x"}):
        assert page.send("PUT", "/formats", bad).status_code == 422, bad
    assert Page(create_app(":memory:")).http.put("/api/asymille/formats", json={"name": "x", "format": {}}).status_code == 403          # not the page's own request


# ── computing ────────────────────────────────────────────────────────────────
X = np.linspace(0, 20, 200)
Y = 4 * np.exp(-(X - 7) ** 2 / (2 * 0.8 ** 2)) + 0.3 + 0.02 * X + np.random.default_rng(1).normal(0, 0.05, X.size)
MODEL = {"components": [{"id": "p1", "fn": "gaussian", "params": {}}, {"id": "b1", "fn": "linear", "params": {}}]}


def test_guess_evaluate_fit_through_the_api(page: Page) -> None:
    x, y = X.tolist(), Y.tolist()
    y[50] = None                                                                # an empty cell travels as null
    started = page.post("/model/guess", {"x": x, "y": y, "model": MODEL}).json()["model"]
    assert abs(started["components"][0]["params"]["center"]["value"] - 7) < 0.3
    curve = page.post("/model/evaluate", {"model": started, "x": [0, 7, 20]}).json()
    assert len(curve["y"]) == 3 and set(curve["components"]) == {"p1", "b1"}
    result = page.post("/fit", {"x": x, "y": y, "model": started, "limits": [2, None], "options": {"level": 0.9}}).json()
    params = {p["name"]: p for p in result["params"]}
    assert result["success"] and abs(params["p1_center"]["value"] - 7) < 4 * params["p1_center"]["stderr"] and result["npoints"] == int(np.count_nonzero(X >= 2)) - 1
    assert result["curve"]["band"]["level"] == 0.9 and json.dumps(result)                                   # every number of the answer is JSON: no NaN
    both = page.post("/fit/global", {"datasets": [{"x": x, "y": y}, {"x": x, "y": (2 * Y).tolist()}], "model": started, "shared": ["p1_center", "p1_sigma"]}).json()
    assert len(both["datasets"]) == 2 and both["shared"] == ["p1_center", "p1_sigma"]
    text = page.post("/model/write", {"model": started}).json()["text"]
    assert text.startswith("p1:gaussian(amplitude~") and page.post("/model/parse", {"text": text}).json()["model"] == started


def test_errors_of_x_a_response_and_a_comparison_through_the_api(page: Page) -> None:
    line = {"components": [{"id": "b", "fn": "linear", "params": {}}]}
    x, y = [0.0, 0.9, 1.8, 2.6, 3.3, 4.4, 5.2, 6.1, 6.5, 7.4], [5.9, 5.4, 4.4, 4.6, 3.5, 3.7, 2.8, 2.8, 2.4, 1.5]
    sx, sy = [w ** -0.5 for w in (1000, 1000, 500, 800, 200, 80, 60, 20, 1.8, 1.0)], [w ** -0.5 for w in (1.0, 1.8, 4.0, 8.0, 20, 20, 70, 70, 100, 500)]
    both = page.post("/fit", {"x": x, "y": y, "sigma": sy, "sigma_x": sx, "model": line, "options": {"weights": "instrumental"}}).json()
    assert both["x_errors"] and {p["name"]: round(p["value"], 6) for p in both["params"]} == {"b_slope": -0.480533, "b_intercept": 5.47991}            # York's line
    refused = page.post("/fit", {"x": x, "y": y, "sigma_x": sx, "model": line})
    assert refused.status_code == 422 and "together with errors on y" in refused.json()["error"]["message"]
    t = np.arange(400) * 0.1
    pulse = np.exp(-(t - 3) ** 2 / 0.08)
    decay = np.convolve(pulse / pulse.sum(), 500 * np.exp(-t / 4.0))[:400] + 2
    model = {"components": [{"id": "r1", "fn": "response", "params": {}}, {"id": "e1", "fn": "exp_decay", "params": {"y0": {"value": 0, "vary": False}}}, {"id": "b1", "fn": "constant", "params": {}}]}
    started = page.post("/model/guess", {"x": t.tolist(), "y": decay.tolist(), "model": model}).json()["model"]
    drawn = page.post("/model/evaluate", {"model": started, "x": t.tolist(), "response": pulse.tolist()}).json()
    assert len(drawn["y"]) == 400 and set(drawn["components"]) == {"e1", "b1"}
    result = page.post("/fit", {"x": t.tolist(), "y": decay.tolist(), "response": pulse.tolist(), "model": started}).json()
    assert result["response"] and {p["name"]: round(p["value"], 5) for p in result["params"] if p["vary"]} == {"r1_shift": 0, "e1_A": 500, "e1_tau": 4, "b1_c": 2} and json.dumps(result)
    missing = page.post("/fit", {"x": t.tolist(), "y": decay.tolist(), "model": started})
    assert missing.status_code == 422 and "choose the column that holds it" in missing.json()["error"]["message"]
    said = page.post("/fit/compare", {"fits": [{"name": "one", "ndata": 400, "nvarys": 3, "chisqr": 52.0}, {"name": "two", "ndata": 400, "nvarys": 5, "chisqr": 40.0}]}).json()
    assert said["best"] == "two" and said["tests"][0]["df"] == [2, 395] and said["tests"][0]["p"] < 1e-20 and len(said["fits"]) == 2
    unlike = page.post("/fit/compare", {"fits": [{"name": "one", "ndata": 400, "nvarys": 3, "chisqr": 52.0}, {"name": "two", "ndata": 399, "nvarys": 5, "chisqr": 40.0}]})
    assert unlike.status_code == 422 and "only fits of the same points" in unlike.json()["error"]["message"]
    assert page.post("/fit/compare", {"fits": [{"name": "one", "ndata": 400, "nvarys": 3, "chisqr": 0}, {"name": "two", "ndata": 400, "nvarys": 5, "chisqr": 40.0}]}).status_code == 422


def test_an_operation_and_a_figure_through_the_api(page: Page) -> None:
    out = page.post("/analyse", {"operation": "smooth_savgol", "args": {"window": 11, "order": 3}, "x": X.tolist(), "y": Y.tolist()}).json()
    assert out["sheet"] == "same" and len(out["columns"][0]["values"]) == 200 and "window of 11 points" in out["note"]
    figure = {"width": 80, "height": 60, "font": "Arial", "background": "#ffffff", "items": [{"t": "line", "paths": [[10, 10, 200, 150]], "stroke": "#000000", "width": 1}]}
    made = page.post("/figure", {"figure": figure, "format": "pdf", "name": "my figure/1"}).json()
    assert made["name"] == "my_figure_1.pdf" and made["mime"] == "application/pdf" and base64.b64decode(made["data"]).startswith(b"%PDF") and made["width_mm"] == 80


@pytest.mark.parametrize("path, body, said", [
    ("/fit", {"x": [1, 2, 3], "y": [1, 2, 3], "model": {"components": [{"id": "u", "fn": "expression", "expr": "__import__('os').getcwd()"}]}}, "not a known function"),
    ("/fit", {"x": [1, 2], "y": [1, 2], "model": MODEL}, "parameters vary and only 2 points"),
    ("/model/parse", {"text": "p1:gaussian(center"}, "not closed"),
    ("/analyse", {"operation": "smooth_savgol", "args": {"window": 99999}, "x": [1, 2, 3], "y": [1, 2, 3]}, "between 3 and 10001"),
    ("/analyse", {"operation": "rm_rf", "x": [1, 2], "y": [1, 2]}, "no operation is called"),
    ("/figure", {"figure": {"width": 80, "height": 60, "items": [{"t": "script"}]}}, "is not something this can draw"),
])
def test_what_cannot_be_computed_is_refused_in_words(page: Page, path: str, body: dict, said: str) -> None:
    answer = page.post(path, body)
    assert answer.status_code == 422 and answer.json()["error"]["code"] == "refused" and said in answer.json()["error"]["message"], answer.text


def test_a_request_with_a_field_the_api_does_not_know_is_refused(page: Page) -> None:
    assert page.post("/fit", {"x": [1], "y": [1], "model": MODEL, "code": "import os"}).status_code == 422
    assert page.post("/fit", {"x": [1], "y": [1], "model": MODEL, "options": {"method": "eval"}}).status_code == 422
    assert page.post("/figure", {"figure": {}, "format": "exe"}).status_code == 422


def test_the_page_is_served_with_a_policy_and_its_scripts(page: Page) -> None:
    home = page.http.get("/")
    assert home.status_code == 200 and "nonce-" in home.headers["content-security-policy"] and home.text.startswith("<!doctype html>") and 'src="js/app.js"' in home.text
    for script in ("js/util.js", "js/plot.js", "js/model.js", "js/app.js", "shared/api.js", "shared/account.js"):
        assert page.http.get("/" + script).status_code == 200, script
    assert page.http.get("/examples/NW1051-NW1.txt").status_code == 200
