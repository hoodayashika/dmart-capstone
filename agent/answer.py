"""Synthesize and Ground steps: fixed answer templates, number formats, evidence, grounded_values.

Every compose_* function returns {"text", "grounded", "evidence"}. `grounded` is built from the values
that were fetched or computed (never by scanning the finished text).
"""
import re
from decimal import Decimal, ROUND_HALF_UP

from agent.understand import STORES, PRODUCTS

ALERT_THRESHOLD = "75.00"      # quoted constant: Poor band is below 75% of target

METRIC_LABEL = {
    "revenue_inr": ("revenue", "money"),
    "daily_target_inr": ("target", "money"),
    "footfall": ("footfall", "number"),
    "stockout_hours": ("stockout hours", "number"),
    "discount_pct": ("discount", "percent"),
}
WEATHER_FIELDS = ["temperature_c", "humidity_pct", "wind_kmh", "rain_mm"]


def _d2(value):
    """Decimal rounded half-up to 2 decimals, as a string without separators."""
    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _d1(value):
    return str(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def fmt_metric(metric, value):
    """Return (text as written in the reply, grounded string)."""
    kind = METRIC_LABEL[metric][1]
    num = _d2(value)
    if kind == "money":
        return f"INR {num}", num
    if kind == "percent":
        return f"{num}%", num
    return num, num


def _when(single=None, rng=None):
    if single:
        return single
    return f"{rng[0]} to {rng[1]}"


def _evidence(source, fields, store, when):
    return {"source": source, "fields": list(fields), "store": store, "date": when}


# ------------------------------------------------------------------ data replies
def compose_lookup(store, metric, value, single=None, rng=None):
    label = METRIC_LABEL[metric][0]
    text_v, g = fmt_metric(metric, value)
    if single:
        text = f"{store}'s {label} on {single} was {text_v}."
    else:
        text = f"{store}'s average {label} between {rng[0]} and {rng[1]} was {text_v}."
    return {"text": text, "grounded": [g],
            "evidence": [_evidence("store_daily", [metric], store, _when(single, rng))]}


def compose_target_vs_actual(store, day, record):
    rev, g_rev = fmt_metric("revenue_inr", record["revenue_inr"])
    tgt, g_tgt = fmt_metric("daily_target_inr", record["daily_target_inr"])
    ach = _d2(record["achievement_pct"])
    band = record["performance_band"]
    text = (f"{store}'s revenue on {day} was {rev} against a target of {tgt}, "
            f"achievement {ach}%, performance band {band}.")
    grounded = [g_rev, g_tgt, ach]
    drafted = band == "Poor"
    if drafted:
        text += (f" Alert: achievement is below the {ALERT_THRESHOLD}% threshold, so this reply is a draft "
                 f"held for human approval.")
        grounded.append(ALERT_THRESHOLD)
    ev = [_evidence("store_daily", ["revenue_inr", "daily_target_inr", "achievement_pct", "performance_band"],
                    store, day)]
    return {"text": text, "grounded": grounded, "evidence": ev, "drafted": drafted}


def compose_comparison(metric, ranking, order, single=None, rng=None):
    label = METRIC_LABEL[metric][0]
    parts, grounded = [], []
    for store, val in ranking:
        t, g = fmt_metric(metric, val)
        parts.append(f"{store} {t}")
        grounded.append(g)
    when = f"on {single}" if single else f"between {rng[0]} and {rng[1]}"
    first = "highest first" if order == "desc" else "lowest first"
    top_word = "Highest" if order == "desc" else "Lowest"
    text = (f"Average {label} per store {when}, {first}: " + "; ".join(parts) +
            f". {top_word}: {ranking[0][0]}.")
    return {"text": text, "grounded": grounded,
            "evidence": [_evidence("store_daily", [metric], "all", _when(single, rng))]}


def compose_inventory(product, store, below):
    fields = ["stock_units", "reorder_threshold"]
    if not below:
        where = f" in {store}" if store else ""
        text = f"No store is below its reorder threshold for {product}{where}."
        return {"text": text, "grounded": [],
                "evidence": [_evidence("inventory", fields, store or "all", None)]}
    parts, grounded = [], []
    for s, units, thr in below:
        parts.append(f"{s} has {units} units against a reorder threshold of {thr}")
        grounded += [str(units), str(thr)]
    text = f"Below the reorder threshold for {product}: " + "; ".join(parts) + "."
    return {"text": text, "grounded": grounded,
            "evidence": [_evidence("inventory", fields, store or "all", None)]}


def compose_feedback(store, data):
    grounded = []
    if data["avg_rating"] is None:
        text = f"{store} has no rated feedback rows"
    else:
        avg = _d2(data["avg_rating"])
        text = f"{store} feedback: average rating {avg} from {data['rated']} rated of {data['total']} feedback rows"
        grounded += [avg, str(data["rated"]), str(data["total"])]
    text += f". Most frequent theme: {data['top_theme']}."
    return {"text": text, "grounded": grounded,
            "evidence": [_evidence("feedback", ["rating", "theme"], store, None)]}


def weather_values(w):
    """(text fragment, grounded list) for a successful weather result."""
    t, h, wd, r = (_d1(w["temperature_c"]), _d1(w["humidity_pct"]), _d1(w["wind_kmh"]), _d1(w["rain_mm"]))
    text = f"temperature {t} C, humidity {h}%, wind {wd} km/h, rain {r} mm"
    return text, [t, h, wd, r]


def weather_evidence(store, day):
    return _evidence("weather_tool", WEATHER_FIELDS, store, day)


def compose_weather(store, day, w):
    frag, grounded = weather_values(w)
    return {"text": f"Weather in {store} on {day}: {frag}.", "grounded": grounded,
            "evidence": [weather_evidence(store, day)]}


def add_weather(reply, store, day, w):
    """Append weather (or a fixed note when the tool failed) to a lookup / target_vs_actual reply."""
    if w.get("ok"):
        frag, grounded = weather_values(w)
        reply["text"] += f" Weather in {store} on {day}: {frag}."
        reply["grounded"] = reply["grounded"] + grounded
        reply["evidence"] = reply["evidence"] + [weather_evidence(store, day)]
    else:
        reply["text"] += " Weather data could not be retrieved for that day."
    return reply


# ------------------------------------------------------------------ non-data replies
def _plain(text):
    return {"text": text, "grounded": [], "evidence": []}


def compose_unsupported():
    return _plain("That field is not available. I can only report these approved fields: revenue, target, "
                  "footfall, stockout hours, discount, achievement, performance band, stock units, reorder "
                  "threshold, rating and feedback theme.")


def compose_out_of_scope():
    return _plain("That is out of scope for this assistant, so I have escalated it instead of answering. I can "
                  "answer questions on revenue, targets, footfall, stockouts, discounts, inventory, feedback and "
                  "weather for the five stores, and I cannot send messages, order stock or change my rules.")


def compose_diagnostic():
    return _plain("Why and trend questions need an analyst, because this assistant reports figures but does not "
                  "explain causes. I have escalated this question to an analyst.")


def compose_clarification(u):
    asks = []
    unresolved = u.get("unresolved") or {}
    if u.get("ambiguous"):
        kind = u["ambiguous"]["kind"]
        opts = u["ambiguous"]["options"]
        if kind == "metric":
            nice = [METRIC_LABEL[m][0] for m in opts]
            asks.append("Which metric do you mean: " + " or ".join(nice) + "? Please ask for one at a time.")
        else:
            asks.append("Which store do you mean: " + " or ".join(opts) + "? Please ask for one at a time.")
    if unresolved.get("store"):
        asks.append(f"I could not match the store name {unresolved['store']}. Which store do you mean? "
                    f"The stores are {', '.join(STORES[:-1])} and {STORES[-1]}.")
    elif "store" in u.get("missing", []):
        asks.append(f"Which store do you mean? The stores are {', '.join(STORES[:-1])} and {STORES[-1]}.")
    if "metric" in u.get("missing", []):
        asks.append("Which metric do you want: revenue, target, footfall, stockout hours or discount?")
    if unresolved.get("date"):
        asks.append("I could not use the date you gave, because it is outside the supported date formats. "
                    "Which date or range do you mean? "
                    f"Use YYYY-MM-DD, D Month YYYY, yesterday, or between <date> and <date>.")
    elif "date" in u.get("missing", []):
        asks.append("Which date or range do you mean? Use YYYY-MM-DD, D Month YYYY, yesterday, or "
                    "between <date> and <date>.")
    if "product" in u.get("missing", []):
        asks.append("Which product do you mean? The products are " + ", ".join(PRODUCTS[:-1]) +
                    " and " + PRODUCTS[-1] + ".")
    if not asks:
        asks.append("Could you rephrase the question with a store, a metric and a date?")
    return _plain(" ".join(asks))


def compose_safe_failure_message(message):
    return _plain(message)


def compose_no_record():
    return _plain("No record was found for that request, so I cannot report a figure.")


def compose_escalated_failure():
    return _plain("The data query failed after three attempts, so I have escalated this to the support team "
                  "instead of guessing a figure.")


# ------------------------------------------------------------------ grounding check
_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
_PRODUCT_RE = re.compile("|".join(re.escape(p) for p in sorted(PRODUCTS, key=len, reverse=True)), re.I)
_NUM = re.compile(r"\d+(?:\.\d+)?")


def count_ungrounded(text, grounded):
    """Numbers in the text (after removing ISO dates and sized product names) that match no grounded value."""
    cleaned = _PRODUCT_RE.sub(" ", _ISO.sub(" ", text))
    allowed = set(grounded)
    return sum(1 for n in _NUM.findall(cleaned) if n not in allowed)
