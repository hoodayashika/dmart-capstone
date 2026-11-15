"""Validate and Query steps: approved-field check, SQLite/Python data access, retries.

All SQL values travel as ? parameters. A column name or a sort direction is placed in the SQL text
only after it passed validate_query (approved list) or the ASC/DESC whitelist.
"""
import csv
import os
import sqlite3
from decimal import Decimal, ROUND_HALF_UP, getcontext
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
getcontext().prec = 50

DATA_START = date(2026, 4, 1)
DATA_END = date(2026, 6, 29)
MAX_ATTEMPTS = 3

# The 11 approved reportable metric fields (nothing else may be measured or returned).
APPROVED_FIELDS = {
    "store_daily": ["revenue_inr", "daily_target_inr", "footfall", "stockout_hours", "discount_pct",
                    "achievement_pct", "performance_band"],
    "inventory": ["stock_units", "reorder_threshold"],
    "feedback": ["rating", "theme"],
}
# Key columns: filters, grouping keys and row labels only, never a measured value.
KEY_COLUMNS = {"store", "store_id", "date", "product", "product_id"}
FILTER_OPS = {"=", ">=", "<=", "<", ">"}
DIRECTIONS = {"ASC", "DESC"}


class ApprovedFieldError(Exception):
    """A table or column outside the approved list was requested."""


class QueryFailed(Exception):
    def __init__(self, attempts, executed="", route=""):
        super().__init__(f"query failed after {attempts} attempts")
        self.attempts = attempts
        self.executed = executed
        self.route = route


class NoRecord(Exception):
    """No row exists for the requested product, store or date. Carries route/executed/attempts for the log."""
    def __init__(self, message="", executed="", route="", attempts=1):
        super().__init__(message)
        self.executed = executed
        self.route = route
        self.attempts = attempts


# ------------------------------------------------------------------ validation
def validate_query(table, measured=(), labels=(), filters=(), group_by=()):
    """Raise ApprovedFieldError unless every part of the request is on the approved list."""
    if table not in APPROVED_FIELDS:
        raise ApprovedFieldError(f"table not approved: {table}")
    approved = set(APPROVED_FIELDS[table])
    for col in measured:
        if col not in approved:
            raise ApprovedFieldError(f"field not approved as a measured value: {col}")
    for col in labels:
        if col not in KEY_COLUMNS:
            raise ApprovedFieldError(f"column not allowed as a row label: {col}")
    for col in list(filters) + list(group_by):
        if col not in KEY_COLUMNS and col not in approved:
            raise ApprovedFieldError(f"column not allowed in WHERE/GROUP BY: {col}")


def _check_direction(direction):
    if direction not in DIRECTIONS:
        raise ApprovedFieldError(f"sort direction not allowed: {direction}")
    return direction


# ------------------------------------------------------------------ data loading
_DB = None
_ROWS = None


def _num(v):
    return None if v is None or str(v).strip() == "" else float(v)


def _load():
    """Load the three CSVs (cleaned store_daily, inventory, feedback) into memory and SQLite."""
    global _DB, _ROWS
    if _DB is not None:
        return
    with open(ROOT / "data" / "store_daily_clean.csv", newline="") as f:
        sd = list(csv.DictReader(f))
    with open(ROOT / "data" / "inventory.csv", newline="") as f:
        inv = list(csv.DictReader(f))
    with open(ROOT / "data" / "feedback.csv", newline="") as f:
        fb = list(csv.DictReader(f))

    num_cols = ["footfall", "revenue_inr", "daily_target_inr", "marketing_spend_inr", "stockout_hours",
                "discount_pct", "revenue_per_footfall", "marketing_efficiency", "achievement_pct", "shortfall_inr"]
    for r in sd:
        for c in num_cols:
            r[c] = _num(r[c])
    for r in inv:
        r["stock_units"] = int(r["stock_units"])
        r["reorder_threshold"] = int(r["reorder_threshold"])
    for r in fb:
        r["rating"] = None if str(r["rating"]).strip() == "" else int(float(r["rating"]))

    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("""CREATE TABLE store_daily (date TEXT, store_id TEXT, store TEXT, footfall REAL,
        revenue_inr REAL, daily_target_inr REAL, marketing_spend_inr REAL, stockout_hours REAL,
        discount_pct REAL, revenue_per_footfall REAL, marketing_efficiency REAL, achievement_pct REAL,
        shortfall_inr REAL, weekend_flag TEXT, performance_band TEXT)""")
    db.executemany("INSERT INTO store_daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   [(r["date"], r["store_id"], r["store"], r["footfall"], r["revenue_inr"], r["daily_target_inr"],
                     r["marketing_spend_inr"], r["stockout_hours"], r["discount_pct"], r["revenue_per_footfall"],
                     r["marketing_efficiency"], r["achievement_pct"], r["shortfall_inr"], r["weekend_flag"],
                     r["performance_band"]) for r in sd])
    db.execute("""CREATE TABLE inventory (store_id TEXT, store TEXT, product_id TEXT, product TEXT,
        stock_units INTEGER, reorder_threshold INTEGER)""")
    db.executemany("INSERT INTO inventory VALUES (?,?,?,?,?,?)",
                   [(r["store_id"], r["store"], r["product_id"], r["product"], r["stock_units"],
                     r["reorder_threshold"]) for r in inv])
    db.execute("""CREATE TABLE feedback (feedback_id TEXT, store_id TEXT, store TEXT, date TEXT,
        rating INTEGER, theme TEXT)""")
    db.executemany("INSERT INTO feedback VALUES (?,?,?,?,?,?)",
                   [(r["feedback_id"], r["store_id"], r["store"], r["date"], r["rating"], r["theme"]) for r in fb])
    db.commit()
    _DB = db
    _ROWS = {(r["store"], r["date"]): r for r in sd}


def get_db():
    _load()
    return _DB


# ------------------------------------------------------------------ retry wrapper
def run_with_retry(fn, executed="", route=""):
    """Run fn up to MAX_ATTEMPTS times. SIMULATE_DB_FAILURES=n fails the first n attempts of every query.
    Returns (result, attempts). Raises QueryFailed after the last attempt, ApprovedFieldError immediately."""
    try:
        n_fail = int(os.environ.get("SIMULATE_DB_FAILURES", "0") or 0)
    except ValueError:
        n_fail = 0
    attempts = 0
    while attempts < MAX_ATTEMPTS:
        attempts += 1
        try:
            if attempts <= n_fail:
                raise RuntimeError("simulated database failure")
            return fn(), attempts
        except ApprovedFieldError:
            raise
        except NoRecord as e:
            e.executed, e.route, e.attempts = executed, route, attempts
            raise
        except Exception:
            continue
    raise QueryFailed(attempts, executed, route)


# ------------------------------------------------------------------ date checks
def check_dates(single=None, rng=None):
    """Return None if every date is inside the data range, else the Safe Failure message."""
    ds = [single] if single else list(rng or [])
    for d in ds:
        dd = date.fromisoformat(d)
        if dd < DATA_START or dd > DATA_END:
            return (f"Date {d} is outside the available data. The data covers "
                    f"{DATA_START.isoformat()} to {DATA_END.isoformat()}.")
    return None


# ------------------------------------------------------------------ rounding
def mean_half_up(count, cents):
    """Exact mean of values stored as whole cents, rounded half-up to 2 decimals (Decimal)."""
    return (Decimal(cents) / Decimal(100) / Decimal(count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ------------------------------------------------------------------ Python-function queries
def get_value(store, day, metric):
    """One value for one store on one date (Python function, not SQL)."""
    validate_query("store_daily", measured=[metric], labels=[], filters=["store", "date"])
    _load()
    row = _ROWS.get((store, day))
    if row is None or row[metric] is None:
        raise NoRecord(f"no row for {store} on {day}")
    return row[metric]


def get_target_vs_actual(store, day):
    """Revenue, target, achievement_pct and performance_band for one store and date (Python function)."""
    fields = ["revenue_inr", "daily_target_inr", "achievement_pct", "performance_band"]
    validate_query("store_daily", measured=fields, filters=["store", "date"])
    _load()
    row = _ROWS.get((store, day))
    if row is None:
        raise NoRecord(f"no row for {store} on {day}")
    return {k: row[k] for k in fields}


# ------------------------------------------------------------------ SQL queries
def sql_avg_parts(metric, store=None, start=None, end=None):
    """COUNT and whole-cent SUM of one metric, per store (store=None) or for one store.
    Returns (sql_text, rows). Values only as ? parameters."""
    validate_query("store_daily", measured=[metric], labels=["store"] if store is None else [],
                   filters=["date", "date"] + (["store"] if store else []),
                   group_by=["store"] if store is None else [])
    parts = f"COUNT({metric}) AS n, SUM(CAST(ROUND({metric} * 100) AS INTEGER)) AS cents"
    if store is None:
        sql = (f"SELECT store, {parts} FROM store_daily WHERE date >= ? AND date <= ? "
               f"GROUP BY store ORDER BY store {_check_direction('ASC')}")
        params = (start, end)
    else:
        sql = f"SELECT {parts} FROM store_daily WHERE store = ? AND date >= ? AND date <= ?"
        params = (store, start, end)
    return sql, params


def run_sql(sql, params):
    db = get_db()
    return db.execute(sql, params).fetchall()


def sql_inventory_below(product, store=None):
    validate_query("inventory", measured=["stock_units", "reorder_threshold"], labels=["store"],
                   filters=["product", "stock_units", "reorder_threshold"] + (["store"] if store else []))
    sql = ("SELECT store, stock_units, reorder_threshold FROM inventory WHERE product = ? "
           "AND stock_units < reorder_threshold")
    params = [product]
    if store:
        sql += " AND store = ?"
        params.append(store)
    sql += f" ORDER BY store {_check_direction('ASC')}"
    return sql, tuple(params)


def sql_inventory_exists(product, store=None):
    validate_query("inventory", measured=["stock_units"], filters=["product"] + (["store"] if store else []))
    sql = "SELECT COUNT(stock_units) FROM inventory WHERE product = ?"
    params = [product]
    if store:
        sql += " AND store = ?"
        params.append(store)
    return sql, tuple(params)


def sql_feedback_rating(store):
    validate_query("feedback", measured=["rating"], filters=["store"])
    sql = ("SELECT COUNT(rating) AS rated, COUNT(*) AS total, "
           "SUM(CAST(ROUND(rating * 100) AS INTEGER)) AS cents FROM feedback WHERE store = ?")
    return sql, (store,)


def sql_feedback_themes(store):
    validate_query("feedback", measured=["theme"], filters=["store"], group_by=["theme"])
    sql = "SELECT theme, COUNT(theme) AS n FROM feedback WHERE store = ? GROUP BY theme"
    return sql, (store,)


# ------------------------------------------------------------------ intent-level fetchers
def fetch_lookup_single(store, day, metric):
    ex = "get_value(store, date, metric)"
    result, attempts = run_with_retry(lambda: get_value(store, day, metric), ex, "python")
    return {"value": result, "attempts": attempts, "executed": ex, "route": "python"}


def fetch_lookup_range(store, metric, start, end):
    sql, params = sql_avg_parts(metric, store=store, start=start, end=end)
    rows, attempts = run_with_retry(lambda: run_sql(sql, params), sql, "sql")
    n, cents = rows[0]
    if not n:
        raise NoRecord("no rows in range", sql, "sql", attempts)
    return {"value": mean_half_up(n, cents), "attempts": attempts, "executed": sql, "route": "sql"}


def fetch_target_vs_actual(store, day):
    ex = "get_target_vs_actual(store, date)"
    result, attempts = run_with_retry(lambda: get_target_vs_actual(store, day), ex, "python")
    return {"record": result, "attempts": attempts, "executed": ex, "route": "python"}


def fetch_comparison(metric, start, end, order):
    sql, params = sql_avg_parts(metric, store=None, start=start, end=end)
    rows, attempts = run_with_retry(lambda: run_sql(sql, params), sql, "sql")
    ranked = [(store, mean_half_up(n, cents)) for store, n, cents in rows if n]
    if not ranked:
        raise NoRecord("no rows in range", sql, "sql", attempts)
    # ties (equal at 2 decimals) are sorted by store name whatever the direction
    ranked.sort(key=lambda t: (-t[1] if order == "desc" else t[1], t[0]))
    return {"ranking": ranked, "attempts": attempts, "executed": sql, "route": "sql"}


def fetch_inventory(product, store=None):
    sql_e, p_e = sql_inventory_exists(product, store)
    exists, att1 = run_with_retry(lambda: run_sql(sql_e, p_e)[0][0], sql_e, "sql")
    if not exists:
        raise NoRecord("no inventory row", sql_e, "sql", att1)
    sql, params = sql_inventory_below(product, store)
    rows, att2 = run_with_retry(lambda: run_sql(sql, params), sql, "sql")
    return {"below": [(s, int(u), int(t)) for s, u, t in rows], "attempts": max(att1, att2),
            "executed": sql, "route": "sql"}


def fetch_feedback(store):
    sql1, p1 = sql_feedback_rating(store)
    (rated, total, cents), att1 = run_with_retry(lambda: run_sql(sql1, p1)[0], sql1, "sql")
    if not total:
        raise NoRecord("no feedback rows", sql1, "sql", att1)
    sql2, p2 = sql_feedback_themes(store)
    themes, att2 = run_with_retry(lambda: run_sql(sql2, p2), sql2, "sql")
    top = sorted(themes, key=lambda t: (-t[1], t[0]))[0][0]
    avg = mean_half_up(rated, cents) if rated else None
    return {"avg_rating": avg, "rated": int(rated), "total": int(total), "top_theme": top,
            "attempts": max(att1, att2), "executed": sql1 + " ; " + sql2, "route": "sql"}
