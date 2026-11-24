"""Agent demo: a small local web page over the agent loop, for demonstrating it.

A run here is one question, one time; nothing is measured or saved. The loop
is `agent_loop.run_question` with its planners and tools; this file only
serves a page and shows each step as the loop executes it.

    .venv/bin/python chapters/ch10/demo/serve.py --check   # is everything there?
    .venv/bin/python chapters/ch10/demo/serve.py           # then http://localhost:8765

Endpoints:
    GET  /                          the page
    GET  /api/questions?split=test  [{question_id, anchor_title, shape, pool_size, featured}] — FEATURED first
    POST /api/run                   {question_id, planner, surface, k, shape,
                                     split, oracle} -> {run_id}; 409 while
                                     another run is going
    GET  /api/runs/<run_id>         {status, steps, result, error}
    GET  /api/status                {key, vespa, build, questions, model}
    GET  /api/skill                 {path, text, generated_by}: the catalogue
                                     description a query-surface run sends,
                                     read from the same file; 404 when missing
    GET  /api/prompt?surface=tools|query
                                    {surface, system, user_template, questions,
                                     given_products_text, notes, source}: the
                                     instructions the llm planner sends, built
                                     as agent_loop.LlmPlanner builds them; 400
                                     for another surface
    POST /api/key                   {key} -> kept in this process's memory only,
                                     for the llm planner, when neither the
                                     environment nor .env has one

The model key: the environment's OPENAI_API_KEY, else the repository's .env
(both read by `agent_loop.load_api_key`), else a key typed into the
page. A typed key lives in this process's memory and nowhere else: it is not
written, logged, or returned by any endpoint, and it is gone when the server
stops.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
CHAPTER = HERE.parent
ROOT = CHAPTER.parents[1]
sys.path.insert(0, str(ROOT / "shared" / "tools"))
sys.path.insert(0, str(CHAPTER))
import builds        # noqa: E402
from query import Vespa   # noqa: E402

import agent_loop    # noqa: E402

PORT = 8765
# The page's Skill is the demo kit's own copy, generated the same way as
# chapters/ch10/expected/skill.md but with no chapter label beside the example
# statements and a note that states the catalogue's measurements as facts:
#   .venv/bin/python chapters/ch10/schema_skill.py --app chapters/ch10/app --profiles hybrid_rrf,bm25_tuned,semantic --statement-labels none --note '<the note in chapters/ch10/demo/README.md>' --out chapters/ch10/demo/skill.md
# (chapters/ch10/demo/README.md has the command with its note in full.)
# Questions listed first on the page, in this order (strings: question ids as the set carries them).
# 1230 the skillet (the walkthrough opens with it), 16911 a tea-length dress (a clothing anchor, asked
# for by the authors), 184 the Thermos bottle (the brands shape, the fallback), 230 the Sony earbuds
# (the spare), 8139 a second dress. Demo-only: the question set itself is not reordered.
FEATURED = ("1230", "16911", "184", "230", "8139")
DEFAULT_SKILL = HERE / "skill.md"
SKILL_GENERATOR = ("chapters/ch10/schema_skill.py --app chapters/ch10/app "
                   "--profiles hybrid_rrf,bm25_tuned,semantic --statement-labels none "
                   "--note '...' --out chapters/ch10/demo/skill.md")
# the per-turn placeholders /api/prompt marks in the user message's template
PROMPT_SYSTEM = "<system text>"
PROMPT_QUESTION = "<question>"
PROMPT_EVIDENCE = "<evidence>"
PROMPT_LEFT = "<turns left>"
PROMPT_LAST = "<last turn>"
KS = (3, 20)
ORACLES = ("none", "facts", "products")
# what the page reads off the final record
RESULT_KEYS = ("question_id", "planner", "surface", "shape", "k", "oracle_mode",
               "answer", "success", "brand_recall", "brand_precision",
               "queries_issued", "context_bytes", "error")


class DemoError(Exception):
    """A request the server refuses, with the HTTP status to answer."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------- live steps

_current = threading.local()     # the run whose thread is executing, if any
_original_execute = agent_loop.execute


def _live_execute(client, action, k, pool=None, surface="tools", tenant=None):
    """`agent_loop.execute`, recording the step on the run of this thread.

    The step is appended before the engine is asked (status `running`) and
    completed when the answer comes back, so the page sees it as it happens.
    Titles come from the result itself (search hits carry id, title and
    brand; a lookup carries the document), so no second request is made. A
    statement with a grouping tail returns products and brand counts: the
    step shows the products, then the counts."""
    run = getattr(_current, "run", None)
    if run is None:
        return _original_execute(client, action, k, pool, surface, tenant)
    args = dict(action.get("args") or {})
    step = {"step": len(run["steps"]) + 1, "tool": action.get("tool"),
            "args": args, "status": "running"}
    with run["lock"]:
        if "pending_llm_ms" in run:
            step["llm_ms"] = run.pop("pending_llm_ms")
        run["steps"].append(step)
    started = time.perf_counter()
    result = _original_execute(client, action, k, pool, surface, tenant)
    ms = (time.perf_counter() - started) * 1000
    tops: list[dict] = []
    if result.get("hits"):
        tops = [{"id": h.get("id"), "title": h.get("title", ""), "brand": h.get("brand", "")}
                for h in result["hits"][:5]]
    if result.get("groups"):
        tops += [{"id": f"{g['value']}:{g['count']}", "title": "", "brand": g["value"]}
                 for g in result["groups"][:5]]
    if not tops and result.get("document"):
        d = result["document"]
        tops = [{"id": d.get("id"), "title": d.get("title", ""), "brand": d.get("brand", "")}]
    with run["lock"]:
        step.update({"status": result.get("status"), "top": tops, "ms": round(ms, 1),
                     "requests": len(result.get("requests", []))})
        if action.get("tool") == "query":
            step["yql_sent"] = result.get("yql")
        if result.get("message"):
            step["message"] = result["message"]
    return result


agent_loop.execute = _live_execute


class _Watched:
    """A planner seen from outside: marks the run `thinking` while it decides,
    and records a final answer or an error as a step when it gives one."""

    def __init__(self, planner, run: dict):
        self.planner, self.run = planner, run
        self.name = planner.name

    def next_action(self, question, evidence):
        with self.run["lock"]:
            self.run["phase"] = "planner"
        action = self.planner.next_action(question, evidence)
        trace = action.get("trace") or {}
        with self.run["lock"]:
            self.run["phase"] = "engine"
            if action["tool"] in ("final", "error"):
                step = {"step": len(self.run["steps"]) + 1, "tool": action["tool"],
                        "status": "done" if action["tool"] == "final" else "error"}
                if action["tool"] == "final":
                    step["answer"] = action.get("final_answer")
                else:
                    step["error"] = action.get("error")
                if "llm_ms" in trace:
                    step["llm_ms"] = trace["llm_ms"]
                self.run["steps"].append(step)
            elif "llm_ms" in trace:
                self.run["pending_llm_ms"] = trace["llm_ms"]
        return action


# ---------------------------------------------------------------- state

FIX_CONTAINER = "./bootstrap.sh ch10   (from the repository root)"
FIX_QUESTIONS = (".venv/bin/python chapters/ch10/build_multihop_set.py --split test "
                 "--threshold 3 > /dev/null")
FIX_KEY = (f"put {agent_loop.KEY_NAME}=<your key> in the repository's .env, or type "
           "it into the page's key box (needed for the llm planner only)")
MAX_KEY_CHARS = 512


class Demo:
    def __init__(self, endpoint: str, build: Path | None, skill_path: Path):
        self.endpoint = endpoint
        try:
            self.build: Path | None = build or builds.latest()
        except SystemExit:
            self.build = None      # reported by status() and --check
        self.skill_path = skill_path
        self.client = Vespa(endpoint)
        self.runs: dict[str, dict] = {}
        self.busy = threading.Lock()
        self.ids = itertools.count(1)
        self._questions: dict[str, list[dict]] = {}
        self._session_key: str | None = None    # memory only; see the docstring

    # -- the key ---------------------------------------------------------
    def key_source(self) -> str:
        """Where the llm planner's key would come from: `env`, `.env`,
        `session` (typed into the page) or `none`.
        `agent_loop.load_api_key` decides between the first two."""
        if os.environ.get(agent_loop.KEY_NAME):
            return "env"
        try:
            agent_loop.load_api_key()
            return ".env"
        except SystemExit:
            pass
        return "session" if self._session_key else "none"

    def set_session_key(self, key) -> None:
        if self.key_source() in ("env", ".env"):
            raise DemoError(409, "a key is already set from the environment or .env; "
                                 "it is the one used")
        if not isinstance(key, str) or not key.strip():
            raise DemoError(400, "the key is empty")
        key = key.strip()
        if len(key) > MAX_KEY_CHARS or any(c.isspace() for c in key):
            raise DemoError(400, "that does not look like a key (spaces, or too long)")
        self._session_key = key

    def _llm_planner(self, shape: str, k: int, surface: str, skill: str | None):
        if self.key_source() == "session":
            # the planner reads its key through `load_api_key`; for this one
            # construction it is the key typed into the page
            original = agent_loop.load_api_key
            agent_loop.load_api_key = lambda: self._session_key
            try:
                return agent_loop.LlmPlanner(shape, k, agent_loop.API_URL, agent_loop.MODEL,
                                             surface=surface, skill=skill)
            finally:
                agent_loop.load_api_key = original
        return agent_loop.LlmPlanner(shape, k, agent_loop.API_URL, agent_loop.MODEL,
                                     surface=surface, skill=skill)

    # -- status ----------------------------------------------------------
    def status(self) -> dict:
        vespa: dict
        if not self.client.healthy():
            vespa = {"up": False, "error": f"no Vespa answers at {self.endpoint}"}
        else:
            try:
                documents = self.client.count("product")
            except Exception as exc:   # noqa: BLE001 - reported, not raised
                documents, error = None, f"{type(exc).__name__}: {str(exc)[:200]}"
            else:
                error = None
            vespa = {"up": True, "version": agent_loop.vespa_version(self.endpoint),
                     "documents": documents}
            if error:
                vespa["error"] = error
        questions = bool(self.build and (self.build / "multihop_test.jsonl").exists())
        return {"key": self.key_source(), "vespa": vespa,
                "build": "present" if self.build else "missing",
                "questions": "present" if questions else "missing",
                "model": agent_loop.MODEL, "endpoint": self.endpoint}

    def skill(self) -> dict:
        """The description a query-surface run gives the model: the same file
        `start` reads, as it is on disk now."""
        path = self.skill_path.resolve()
        try:
            shown = str(path.relative_to(ROOT))
        except ValueError:
            shown = str(self.skill_path)
        try:
            text = path.read_text()
        except OSError:
            raise DemoError(404, f"no skill file at {shown}; generate it with "
                                 f"{SKILL_GENERATOR} (chapters/ch10/demo/README.md has "
                                 "the command with its note), or pass --skill PATH") from None
        return {"path": shown, "text": text, "generated_by": SKILL_GENERATOR}

    def prompt(self, surface: str) -> dict:
        """What the llm planner tells the model on `surface`, built the way
        `agent_loop.LlmPlanner.build_prompt` builds it (its constants, its
        substitutions in its order, its `render_tools` and `question_text`),
        without a key or a model call. `system` is the exact text; the
        per-turn part depends on the run, so it is a template with its
        placeholders in angle brackets."""
        if surface not in agent_loop.SURFACES:
            raise DemoError(400, "surface must be tools or query")
        planner = SimpleNamespace(surface=surface)
        if surface == "query":
            system = agent_loop.SYSTEM_TEXT_QUERY.replace("{skill}",
                                                          self.skill()["text"].rstrip())
        else:
            system = agent_loop.SYSTEM_TEXT
        system = system.replace("{tools}", agent_loop.LlmPlanner.render_tools(planner))
        questions = {shape: agent_loop.LlmPlanner.question_text(
                         SimpleNamespace(shape=shape), {"anchor_title": "<anchor title>"})
                     for shape in agent_loop.SHAPES}
        return {
            "surface": surface,
            "system": system,
            "user_template": (PROMPT_SYSTEM + "\n\nQuestion: " + PROMPT_QUESTION + "\n\n"
                              "Evidence so far (JSON):\n" + PROMPT_EVIDENCE + "\n\n"
                              "Turns left: " + PROMPT_LEFT + "." + PROMPT_LAST
                              + " Reply with one JSON action."),
            "questions": questions,
            "given_products_text": agent_loop.GIVEN_PRODUCTS_TEXT,
            "notes": [
                f"The whole text is sent each turn as one user message, with the action's "
                f"JSON schema as the reply format; {PROMPT_SYSTEM} is the text above.",
                f"{PROMPT_QUESTION}: the question for the shape chosen (below), with the "
                "anchor product's title in it.",
                f"{PROMPT_EVIDENCE}: every tool call so far and its result, as JSON; "
                "[] on the first turn.",
                f"{PROMPT_LEFT}: {agent_loop.MAX_STEPS} on the first turn, one fewer after "
                f"each tool call. {PROMPT_LAST}: on the last turn, \" This is your last "
                "turn: reply with the final answer now.\"; otherwise nothing.",
                "Handing over the answer set's products adds one paragraph to the end of "
                "the text above (given_products_text).",
            ],
            "source": "chapters/ch10/agent_loop.py",
        }

    def questions(self, split: str) -> list[dict]:
        if split not in builds.SPLITS:
            raise DemoError(400, f"split must be one of {', '.join(builds.SPLITS)}")
        if self.build is None:
            raise DemoError(503, f"no catalogue build; make one: {FIX_CONTAINER}")
        if split not in self._questions:
            try:
                qs = agent_loop.load_questions(self.build, split, None)
            except SystemExit:
                raise DemoError(503, f"no {split} question set in the catalogue build; make it: "
                                     + FIX_QUESTIONS.replace("--split test", f"--split {split}")
                                     ) from None
            # the order main() gives them: by query id
            self._questions[split] = sorted(
                qs, key=lambda q: (0, int(q["query_id"])) if q["query_id"].isdigit()
                else (1, q["query_id"]))
        return self._questions[split]

    def question_list(self, split: str) -> list[dict]:
        # the featured questions first, in FEATURED's order (the ones a presenter reaches for: the
        # walkthrough's three and a clothing anchor), then the rest in the set's own order
        qs = self.questions(split)
        rank = {str(q): i for i, q in enumerate(FEATURED)}
        ordered = sorted(qs, key=lambda q: (rank.get(str(q["question_id"]), len(FEATURED))))
        return [{"question_id": q["question_id"], "anchor_title": q["anchor_title"],
                 "shape": q.get("shape", list(agent_loop.SHAPES)),
                 "pool_size": len(q.get("pool") or []),
                 "featured": str(q["question_id"]) in rank} for q in ordered]

    def start(self, body: dict) -> str:
        split = body.get("split") or "test"
        qid = str(body.get("question_id") or "")
        question = next((q for q in self.questions(split) if q["question_id"] == qid), None)
        if question is None:
            raise DemoError(400, f"no question {qid!r} in the {split} split")
        planner_name = body.get("planner") or "rules"
        surface = body.get("surface") or "tools"
        shape = body.get("shape") or "alternative"
        oracle = body.get("oracle") or "none"
        try:
            k = int(body.get("k") or 3)
        except (TypeError, ValueError):
            raise DemoError(400, "k must be a number") from None
        if planner_name not in ("rules", "llm"):
            raise DemoError(400, "planner must be rules or llm")
        if surface not in agent_loop.SURFACES:
            raise DemoError(400, "surface must be tools or query")
        if surface == "query" and planner_name != "llm":
            raise DemoError(400, "the query surface is for the llm planner; "
                                 "the rules planner works the tools")
        if shape not in agent_loop.SHAPES:
            raise DemoError(400, "shape must be alternative or brands")
        if k not in KS:
            raise DemoError(400, f"k must be one of {KS}")
        if oracle not in ORACLES:
            raise DemoError(400, f"oracle must be one of {ORACLES}")
        if oracle == "products" and shape != "alternative":
            raise DemoError(400, "the oracle's products are for shape alternative")

        if not self.busy.acquire(blocking=False):
            raise DemoError(409, "another run is going; wait for it to finish")
        try:
            skill = self.skill_path.read_text() if surface == "query" else None
            if planner_name == "rules":
                planner = agent_loop.RulesPlanner(shape, k)
            else:
                try:
                    planner = self._llm_planner(shape, k, surface, skill)
                except SystemExit:
                    raise DemoError(400, f"the llm planner needs a model key: {FIX_KEY}"
                                    ) from None
            if not self.client.healthy():
                raise DemoError(503, f"no Vespa at {self.endpoint}; start the "
                                     f"container first: {FIX_CONTAINER}")
        except BaseException:
            self.busy.release()
            raise

        run_id = str(next(self.ids))
        run = {"status": "running", "phase": "planner", "steps": [], "result": None,
               "error": None, "lock": threading.Lock(),
               "request": {"question_id": qid, "planner": planner_name, "surface": surface,
                           "k": k, "shape": shape, "oracle": oracle, "split": split,
                           "anchor_title": question["anchor_title"]}}
        self.runs[run_id] = run
        threading.Thread(target=self._run, daemon=True,
                         args=(run, question, planner, shape, k, surface, oracle)).start()
        return run_id

    def _run(self, run, question, planner, shape, k, surface, oracle) -> None:
        _current.run = run
        started = time.perf_counter()
        try:
            products = None
            if oracle == "products":
                with run["lock"]:
                    run["phase"] = "reading the oracle's products"
                products = agent_loop.load_products(self.build, set(question["oracle"]))
            record = agent_loop.run_question(
                question, _Watched(planner, run), self.client, shape=shape, k=k,
                oracle=oracle == "facts", surface=surface, oracle_products=products)
            result = {key: record.get(key) for key in RESULT_KEYS}
            result["ms"] = round((time.perf_counter() - started) * 1000, 1)
            result["oracle_size"] = len(question.get("oracle") or [])
            with run["lock"]:
                run["result"] = result
                run["status"] = "done"
        except BaseException as exc:   # noqa: BLE001 - shown on the page, never raised
            with run["lock"]:
                run["status"] = "failed"
                run["error"] = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
        finally:
            _current.run = None
            self.busy.release()

    def view(self, run_id: str) -> dict:
        run = self.runs.get(run_id)
        if run is None:
            raise DemoError(404, f"no run {run_id}")
        with run["lock"]:
            return {key: run[key] for key in
                    ("status", "phase", "steps", "result", "error", "request")}


# ---------------------------------------------------------------- HTTP

def make_handler(demo: Demo):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):   # quiet: one line per run is enough
            pass

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False, default=str).encode(),
                       "application/json; charset=utf-8")

        def do_GET(self):
            url = urlparse(self.path)
            try:
                if url.path in ("/", "/index.html"):
                    self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
                elif url.path == "/api/status":
                    self._json(200, demo.status())
                elif url.path == "/api/skill":
                    self._json(200, demo.skill())
                elif url.path == "/api/prompt":
                    surface = parse_qs(url.query).get("surface", ["tools"])[0]
                    self._json(200, demo.prompt(surface))
                elif url.path == "/api/questions":
                    split = parse_qs(url.query).get("split", ["test"])[0]
                    self._json(200, demo.question_list(split))
                elif url.path.startswith("/api/runs/"):
                    self._json(200, demo.view(url.path.rsplit("/", 1)[1]))
                else:
                    self._json(404, {"error": "not found"})
            except DemoError as exc:
                self._json(exc.status, {"error": str(exc)})

        def do_POST(self):
            path = urlparse(self.path).path
            if path not in ("/api/run", "/api/key"):
                self._json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(body, dict):
                    raise DemoError(400, "the body must be a JSON object")
                if path == "/api/key":
                    # the key is neither printed nor answered back
                    demo.set_session_key(body.get("key"))
                    self._json(200, {"key": demo.key_source()})
                    return
                run_id = demo.start(body)
                print(f"run {run_id}: question {body.get('question_id')}, "
                      f"{body.get('planner')} / {body.get('surface')}", file=sys.stderr)
                self._json(200, {"run_id": run_id})
            except json.JSONDecodeError:
                self._json(400, {"error": "the body is not JSON"})
            except DemoError as exc:
                self._json(exc.status, {"error": str(exc)})

    return Handler


def make_server(demo: Demo, port: int = PORT, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(demo))


def check(demo: Demo) -> int:
    """Print the setup, one line each, with the fix for what is missing.
    Non-zero when the page could not run a question (container down, no
    documents, no build or no question file); a missing key is only a
    warning, since the rules planner needs none."""
    st = demo.status()
    failed = False

    def line(ok: bool | None, text: str, fix: str = "") -> None:
        mark = "ok  " if ok else ("warn" if ok is None else "FAIL")
        print(f"{mark}  {text}" + (f"\n      fix: {fix}" if fix else ""))

    v = st["vespa"]
    if not v["up"]:
        failed = True
        line(False, f"Vespa: {v['error']}", FIX_CONTAINER)
    elif not v.get("documents"):
        failed = True
        line(False, f"Vespa {v['version']} at {st['endpoint']}: no product documents"
             + (f" ({v['error']})" if v.get("error") else ""), FIX_CONTAINER)
    else:
        line(True, f"Vespa {v['version']} at {st['endpoint']}: {v['documents']:,} products")
    if st["build"] == "missing":
        failed = True
        line(False, "catalogue build: missing", FIX_CONTAINER)
    else:
        line(True, "catalogue build: present")
        if st["questions"] == "missing":
            failed = True
            line(False, "question set: missing from the catalogue build", FIX_QUESTIONS)
        else:
            line(True, "question set: present")
    if st["key"] == "none":
        line(None, "model key: none (the rules planner works without one)", FIX_KEY)
    else:
        line(True, f"model key: from {st['key']} (model {st['model']})")
    print("ready" if not failed else "not ready: fix the FAIL lines above, then run --check again")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--endpoint", default="http://localhost:8080")
    ap.add_argument("--build", type=Path, default=None,
                    help="the corpus build (default: the newest)")
    ap.add_argument("--skill", type=Path, default=DEFAULT_SKILL,
                    help="the catalogue description shown on the query surface")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--check", action="store_true",
                    help="print what is set up and what is missing, with the fix; "
                         "exit non-zero when the page could not run a question")
    args = ap.parse_args(argv)
    demo = Demo(args.endpoint, args.build, args.skill)
    if args.check:
        return check(demo)
    server = make_server(demo, args.port)
    print(f"agent demo on http://localhost:{args.port} (Vespa {args.endpoint}, "
          f"catalogue build {'present' if demo.build else 'missing'})", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
