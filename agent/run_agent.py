"""Orchestrator: handle(question, session_id, user_id) runs Interpret -> Route -> Validate -> Query ->
Calculate -> Synthesize -> Ground -> Record and returns the audit record (also appended to the log).

Interactive use:  python agent/run_agent.py
"""
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent import answer, fetch                      # noqa: E402
from agent.understand import understand, empty_context, CLARIFY_THRESHOLD  # noqa: E402
from tools.weather import get_weather                # noqa: E402

SESSIONS = {}                 # session_id -> context (never shared across sessions)
TOKEN_BUDGET = 150


def reset_sessions():
    SESSIONS.clear()


def _needs_clarification(u):
    return bool(u["missing"] or u["unresolved"]["store"] or u["unresolved"]["date"]
                or u["ambiguous"] or u["confidence"] < CLARIFY_THRESHOLD)


def _log_path():
    return os.environ.get("AGENT_LOG_PATH") or str(ROOT / "logs" / "runs.jsonl")


def handle(question, session_id, user_id="u1"):
    t0 = perf_counter()
    ctx = SESSIONS.get(session_id) or empty_context()

    # ---- Interpret
    u = understand(question, ctx)
    intent = u["intent"]
    if intent not in ("unsupported_metric", "diagnostic", "out_of_scope") and u["context_update"]:
        SESSIONS[session_id] = u["context_update"]

    status, reply = None, None
    route, executed, attempts, tool_calls, tools_called = "none", None, 0, 0, []

    # ---- Route + precedence (1) the intent itself
    if intent == "unsupported_metric":
        status, reply = "Safe Failure", answer.compose_unsupported()
    elif intent == "out_of_scope":
        status, reply = "Escalated", answer.compose_out_of_scope()
    elif intent == "diagnostic":
        status, reply = "Escalated", answer.compose_diagnostic()
    # (2) clarification
    elif _needs_clarification(u):
        status, reply = "Clarification Needed", answer.compose_clarification(u)
    else:
        # (3) date range check for the intents that use a date
        msg = None
        if intent in ("lookup", "target_vs_actual", "comparison", "weather"):
            msg = fetch.check_dates(u["date"], u["date_range"])
        if msg:
            status, reply = "Safe Failure", answer.compose_safe_failure_message(msg)
        else:
            # (4) data queries, (5) alert
            try:
                status, reply, route, executed, attempts, tool_calls, tools_called = _run_data(u)
            except fetch.QueryFailed as e:
                status, reply = "Escalated", answer.compose_escalated_failure()
                route, executed, attempts, tool_calls = e.route, e.executed, e.attempts, 1
            except fetch.NoRecord as e:
                status, reply = "Safe Failure", answer.compose_no_record()
                route, executed, attempts, tool_calls = e.route, e.executed, e.attempts, 1
            except fetch.ApprovedFieldError:
                status, reply = "Safe Failure", answer.compose_unsupported()
                route, executed, attempts, tool_calls = "none", None, 0, 0

    # ---- Ground
    text = reply["text"]
    grounded = list(reply["grounded"])
    ungrounded = answer.count_ungrounded(text, grounded)
    tokens_est = len(question.split()) + len(text.split())

    record = {
        "run_id": uuid.uuid4().hex,
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": question,
        "intent": intent,
        "confidence": u["confidence"],
        "route": route,
        "executed": executed,
        "attempts": attempts,
        "tools_called": tools_called,
        "status": status,
        "answer_text": text,
        "evidence": reply["evidence"],
        "grounded_values": grounded,
        "latency_ms": 0.0,
        "tokens_est": tokens_est,
        "tool_calls": tool_calls,
        "ungrounded_numbers": ungrounded,
        "budget_exceeded": tokens_est > TOKEN_BUDGET,
    }
    record["latency_ms"] = round((perf_counter() - t0) * 1000, 3)

    # ---- Record
    path = _log_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")
    return record


def _run_data(u):
    """Query + Calculate + Synthesize for one answerable question."""
    intent = u["intent"]
    store, single, rng = u["store"], u["date"], u["date_range"]
    tools_called, tool_calls = [], 0

    def maybe_weather(rep, route):
        nonlocal tools_called, tool_calls
        if u["weather"] and single and store:          # one store, one date only
            w = get_weather(store, single)
            tools_called, tool_calls = ["weather_tool"], tool_calls + 1
            rep = answer.add_weather(rep, store, single, w)
            route = "python+weather"
        return rep, route

    if intent == "lookup":
        metric = u["metric"]
        if single:
            r = fetch.fetch_lookup_single(store, single, metric)
        else:
            r = fetch.fetch_lookup_range(store, metric, rng[0], rng[1])
        tool_calls = 1
        rep = answer.compose_lookup(store, metric, r["value"], single, rng)
        route = r["route"]
        rep, route = maybe_weather(rep, route)
        return "Answered", rep, route, r["executed"], r["attempts"], tool_calls, tools_called

    if intent == "target_vs_actual":
        r = fetch.fetch_target_vs_actual(store, single)
        tool_calls = 1
        rep = answer.compose_target_vs_actual(store, single, r["record"])
        route = r["route"]
        rep, route = maybe_weather(rep, route)
        status = "Drafted" if rep["drafted"] else "Answered"
        return status, rep, route, r["executed"], r["attempts"], tool_calls, tools_called

    if intent == "comparison":
        start, end = (single, single) if single else rng
        r = fetch.fetch_comparison(u["metric"], start, end, u["order"])
        rep = answer.compose_comparison(u["metric"], r["ranking"], u["order"], single, rng)
        return "Answered", rep, r["route"], r["executed"], r["attempts"], 1, []

    if intent == "inventory":
        r = fetch.fetch_inventory(u["product"], store)
        rep = answer.compose_inventory(u["product"], store, r["below"])
        return "Answered", rep, r["route"], r["executed"], r["attempts"], 1, []

    if intent == "feedback":
        r = fetch.fetch_feedback(store)
        rep = answer.compose_feedback(store, r)
        return "Answered", rep, r["route"], r["executed"], r["attempts"], 1, []

    if intent == "weather":
        w = get_weather(store, single)
        if not w.get("ok"):
            rep = answer.compose_no_record()
            return "Safe Failure", rep, "weather", "tools.weather.get_weather(city, date)", 0, 1, ["weather_tool"]
        rep = answer.compose_weather(store, single, w)
        return "Answered", rep, "weather", "tools.weather.get_weather(city, date)", 0, 1, ["weather_tool"]

    raise RuntimeError(f"unhandled intent {intent}")


if __name__ == "__main__":
    sid = "cli"
    print("Ask a question (blank line to quit).")
    while True:
        try:
            q = input("> ").strip()
        except EOFError:
            break
        if not q:
            break
        out = handle(q, sid)
        print(f"[{out['status']}] {out['answer_text']}")
