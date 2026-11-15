"""Interpret step: turn a plain-English question into structured entities.

understand(question, context) is fully deterministic (rules + difflib), no language model.
"""
import difflib
import re
from datetime import date, timedelta

AS_OF_DATE = date(2026, 6, 30)            # "today" for the data set; yesterday = 2026-06-29
CLARIFY_THRESHOLD = 0.7
UNRESOLVED_CONF = 0.4

STORES = ["Mumbai", "Pune", "Hyderabad", "Bengaluru", "Ahmedabad"]
STORE_ALIASES = {"bangalore": "Bengaluru"}
PRODUCTS = ["Amul Milk 1L", "Toor Dal 1kg", "Basmati Rice 5kg", "Sunflower Oil 1L",
            "Iodised Salt 1kg", "Instant Noodles 70g", "Glucose Biscuits 200g", "Detergent Powder 1kg"]

# ------------------------------------------------------------------ word lists
def _forms(words):
    out = set()
    for w in words:
        out.add(w)
        out.add(w + "s")
        out.add(w + "es")
        if w.endswith("y"):
            out.add(w[:-1] + "ies")
        if w.endswith("s"):
            out.add(w[:-1])
    return out


METRIC_MAP = {
    "revenue": "revenue_inr", "sales": "revenue_inr", "sale": "revenue_inr", "turnover": "revenue_inr",
    "earnings": "revenue_inr", "earning": "revenue_inr",
    "target": "daily_target_inr", "targets": "daily_target_inr",
    "footfall": "footfall", "footfalls": "footfall", "visitors": "footfall", "visitor": "footfall",
    "stockout": "stockout_hours", "stockouts": "stockout_hours",
    "discount": "discount_pct", "discounts": "discount_pct",
}
OVERRIDE_WORDS = _forms(["ignore", "disregard", "override", "bypass", "forget", "send", "email",
                         "whatsapp", "purchase", "buy", "restock"])
UNSUPPORTED_WORDS = _forms(["profit", "margin", "marketing", "cost", "expense", "shortfall",
                            "efficiency", "weekend"])
DIAGNOSTIC_WORDS = _forms(["why", "trend", "reason", "cause"])
FEEDBACK_WORDS = _forms(["feedback", "review", "rating", "theme"])
TARGET_PARTNERS = _forms(["hit", "met", "meet", "miss", "missed", "beat", "exceed", "exceeded", "achieve",
                          "achieved", "reach", "reached", "below", "above", "against", "versus"])
WEATHER_WORDS = _forms(["weather", "rain", "temperature", "humidity", "hot", "cold", "rainfall"])
COMPARISON_WORDS = {"which", "highest", "lowest", "best", "worst"}
INVENTORY_WORDS = {"reorder", "reorders", "inventory", "inventories"}

STOP_WORDS = {"hello", "thanks", "thank", "kindly", "please", "display", "compare", "which", "what", "whats",
              "how", "why", "did", "and", "show", "check", "report", "where", "would", "could", "can", "will",
              "give", "tell", "list"}
PROPER_NOUNS = {"dmart", "avenue", "supermarts", "kavita", "rao", "meteo", "github", "python", "sqlite",
                "postgresql", "markdown"}
BRAND_PERSONA = {"dmart", "avenue", "supermarts", "kavita", "rao"}

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december"]
MONTH_ABBR = {"jan", "feb", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec"}
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
PREPS_FOR_MONTH = {"in", "on", "of", "during", "since", "for", "from", "until", "till", "by", "to",
                   "through", "throughout", "before", "after", "within", "over"}

KEYWORDS = set()
for _ws in (METRIC_MAP.keys(), OVERRIDE_WORDS, UNSUPPORTED_WORDS, DIAGNOSTIC_WORDS, FEEDBACK_WORDS,
            TARGET_PARTNERS, WEATHER_WORDS, COMPARISON_WORDS, INVENTORY_WORDS, STOP_WORDS, MONTHS, WEEKDAYS):
    KEYWORDS |= set(_ws)
KEYWORDS |= _forms(["fall", "short", "achievement", "performance", "band", "average", "mean", "total",
                    "customer", "say", "saying", "place", "order", "per", "stock", "unit", "threshold", "level",
                    "point", "store", "product", "spend", "yesterday", "today", "tomorrow", "week", "month",
                    "quarter", "year", "daily", "weekly", "monthly", "quarterly", "yearly", "annual", "between",
                    "last", "next", "past", "previous", "recent", "latest", "current", "weekday", "range",
                    "hours", "hour", "units", "price", "date", "day", "city"])

TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[sS])?|\d+")


def _tokenize(text):
    """Return a list of (base, possessive, original) for every word/number token."""
    toks = []
    for m in TOKEN_RE.finditer(text):
        t = m.group(0)
        poss = t.endswith("'s") or t.endswith("'S")
        toks.append((t[:-2] if poss else t, poss, t, m.start()))
    return toks


# ------------------------------------------------------------------ dates
_ISO_STRICT = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_ALT = "|".join(MONTHS)
_DMY = re.compile(r"(?<![\w-])(\d{1,2})\s+(" + _MONTH_ALT + r")\s+(\d{4})(?![\w-])", re.I)
_ISO_ANY = re.compile(r"(?<![\w-])(\d{4})-(\d{2})-(\d{2})(?![\w-])")
_DATE_PIECE = r"(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}\s+[A-Za-z]+\s+\d{4})"
_BETWEEN = re.compile(r"\bbetween\s+" + _DATE_PIECE + r"\s+and\s+" + _DATE_PIECE, re.I)


def _real_date(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def _parse_one(piece):
    """Parse one date piece of the closed grammar (strict ISO or D Month YYYY). None when invalid."""
    piece = piece.strip()
    if _ISO_STRICT.match(piece):
        return _real_date(piece[0:4], piece[5:7], piece[8:10])
    m = _DMY.fullmatch(piece)
    if m:
        return _real_date(m.group(3), MONTHS.index(m.group(2).lower()) + 1, m.group(1))
    return None


_UNRESOLVED_PATTERNS = [
    r"\b\d{4}-\d{1,2}-\d{1,2}\b",                 # 2026-5-15 and impossible dates
    r"\b\d{4}-w\d{1,2}(?:-\d)?\b",                # ISO week
    r"\b\d{8}\b",                                 # 20260515
    r"\b\d{1,4}[/.]\d{1,2}[/.]\d{1,4}\b",         # 15/05/2026
    r"\b\d{1,2}-\d{1,2}-\d{2,4}\b",               # 15-05-2026
    r"\b\d{1,2}(?:st|nd|rd|th)\b",                # ordinal day
    r"\b(?:19|20)\d{2}\b",                        # bare year
    r"\bq[1-4]\b", r"\bh[12]\b", r"\bfy\s?\d{2,4}\b",
    r"\b\d+\s*(?:days?|weeks?|months?|years?)\b",
    r"\b(?:today|tomorrow|tonight|ago|past|previous|prior|recent|recently|latest|now|lately|current|"
    r"currently|ytd|mtd|qtd|eod|eom|eoy|eow|morning|afternoon|evening|night|fortnight|week|weeks|month|"
    r"months|quarter|quarters|year|years|season|last|next|upcoming|coming)\b",
]


def parse_dates(question):
    """Closed date grammar. Returns dict(single, range, unresolved, present)."""
    text = question.replace("\u2019", "'")
    work = text
    singles, ranges, unresolved = [], [], []

    # 1. between <date> and <date>
    for m in _BETWEEN.finditer(work):
        a, b = _parse_one(m.group(1)), _parse_one(m.group(2))
        if a and b and a <= b:
            ranges.append((a, b))
        else:
            unresolved.append(m.group(0))
    work = _BETWEEN.sub(" ", work)
    if re.search(r"\bbetween\b", work, re.I):
        unresolved.append("between")

    # 2. valid single dates: D Month YYYY, then ISO
    def take_dmy(m):
        d = _real_date(m.group(3), MONTHS.index(m.group(2).lower()) + 1, m.group(1))
        (singles.append(d) if d else unresolved.append(m.group(0)))
        return " "
    work = _DMY.sub(take_dmy, work)

    def take_iso(m):
        d = _real_date(m.group(1), m.group(2), m.group(3))
        (singles.append(d) if d else unresolved.append(m.group(0)))
        return " "
    work = _ISO_ANY.sub(take_iso, work)

    # 3. yesterday
    if re.search(r"\byesterday\b", work, re.I):
        singles.append(AS_OF_DATE - timedelta(days=1))
        work = re.sub(r"\byesterday\b", " ", work, flags=re.I)

    # 4. frequency phrases are part of a metric phrase, not a date phrase
    work = re.sub(r"\bper\s+(?:day|week|month|year)\b", " ", work, flags=re.I)

    # 5. weekday words
    lowered = work.lower()
    one_date = singles[0] if (len(singles) == 1 and not ranges) else None
    for m in re.finditer(r"\b(" + "|".join(WEEKDAYS) + r"|weekday)(s?)\b", lowered):
        name, plural = m.group(1), m.group(2) == "s"
        if plural and ranges and not singles:
            continue
        if (not plural) and name in WEEKDAYS and one_date and WEEKDAYS[one_date.weekday()] == name:
            continue
        unresolved.append(m.group(0))
    work = re.sub(r"\b(?:" + "|".join(WEEKDAYS) + r"|weekday)s?\b", " ", work, flags=re.I)

    # 6. month names (may / march are verbs unless the rules below say otherwise)
    toks = re.findall(r"[A-Za-z]+", work)
    for i, t in enumerate(toks):
        low = t.lower()
        prev = toks[i - 1].lower() if i > 0 else ""
        nxt = toks[i + 1].lower() if i + 1 < len(toks) else ""
        if low in MONTH_ABBR:
            unresolved.append(t)
        elif low in MONTHS and low not in ("may", "march"):
            unresolved.append(t)
        elif low == "march":
            if t[0].isupper() or prev in PREPS_FOR_MONTH:
                unresolved.append(t)
        elif low == "may":
            if t[0].isupper():
                if nxt not in ("i", "we", "you", "be"):
                    unresolved.append(t)
            elif prev in PREPS_FOR_MONTH:
                unresolved.append(t)

    # 7. everything else that looks like a date or a period
    for pat in _UNRESOLVED_PATTERNS:
        for m in re.finditer(pat, work, re.I):
            unresolved.append(m.group(0))

    # 8. a second date outside "between ... and ..."
    valid_count = len(singles) + len(ranges)
    if valid_count > 1:
        unresolved.append("more than one date")

    seen, uniq = set(), []
    for u in unresolved:
        if u.lower() not in seen:
            seen.add(u.lower())
            uniq.append(u)
    result = {"single": None, "range": None, "unresolved": uniq,
              "present": bool(uniq) or valid_count > 0}
    if not uniq:
        if singles:
            result["single"] = singles[0]
        elif ranges:
            result["range"] = ranges[0]
    return result


# ------------------------------------------------------------------ stores and products
def _similarity(word, store):
    return difflib.SequenceMatcher(None, word.lower(), store.lower()).ratio()


def _find_product(text):
    low = text.lower().replace("_", " ")
    for full in PRODUCTS:
        base = re.sub(r"\s+\d+\s*(?:l|kg|g)$", "", full, flags=re.I).lower()
        size = full.lower()[len(base):].strip()
        pat = r"\b" + re.escape(base) + r"(?:\s*" + re.escape(size) + r")?\b"
        if re.search(pat, low):
            return full, set(base.split())
    return None, set()


def _resolve_stores(toks, product_words, has_metric, has_weather, has_date):
    """Return (resolved list of (store, conf, kind), unresolved list of words)."""
    resolved, candidates = [], []
    for i, (base, poss, orig, _pos) in enumerate(toks):
        low = base.lower()
        if not base.isalpha():
            continue
        prev = toks[i - 1][0].lower() if i > 0 else ""
        exact = next((s for s in STORES if s.lower() == low), None)
        if exact:
            resolved.append((exact, 1.0, "exact"))
            continue
        if low in STORE_ALIASES:
            resolved.append((STORE_ALIASES[low], 1.0, "alias"))
            continue
        if low in BRAND_PERSONA:
            candidates.append({"word": base, "prev": prev, "poss": poss, "brand": True, "score": 0.0})
            continue
        if len(base) < 5 or not (base[0].isupper() or poss):
            continue
        if i == 0 and not poss:
            continue
        if low in KEYWORDS or low in STOP_WORDS or low in PROPER_NOUNS or low in product_words:
            continue
        scores = [(_similarity(low, s), s) for s in STORES]
        best_score, best_store = max(scores)
        candidates.append({"word": base, "prev": prev, "poss": poss, "brand": False,
                           "score": best_score, "store": best_store})

    unresolved = []
    for c in candidates:
        if not c["brand"] and c["score"] >= CLARIFY_THRESHOLD:
            resolved.append((c["store"], round(c["score"], 2), "fuzzy"))
    any_resolved = bool(resolved)
    for c in candidates:
        if not c["brand"] and c["score"] >= CLARIFY_THRESHOLD:
            continue
        if c["brand"]:
            if (not any_resolved) and (c["poss"] or c["prev"] in ("for", "about", "in", "at")):
                unresolved.append(c["word"])
            continue
        rule_a = c["poss"] or c["prev"] in ("and", "or", "vs", "versus", "than", "for")
        rule_b = (not any_resolved) and (c["prev"] in ("about", "in", "at") or has_metric or has_weather or has_date)
        if rule_a or rule_b:
            unresolved.append(c["word"])
    return resolved, unresolved


# ------------------------------------------------------------------ main entry
def empty_context():
    return {"store": None, "metric": None, "date": None, "range": None, "product": None, "tva": False}


def _is_imperative_order(lw, text, i):
    nxt = lw[i + 1] if i + 1 < len(lw) else ""
    if nxt in ("threshold", "thresholds", "level", "levels", "point", "points"):
        return False
    if i == 0:
        return True
    if lw[i - 1] in ("please", "kindly"):
        return True
    if i >= 2 and (lw[i - 2], lw[i - 1]) in {("can", "you"), ("could", "you"), ("will", "you"), ("would", "you")}:
        return True
    if i >= 3 and lw[i - 3:i] == ["go", "ahead", "and"]:
        return True
    return False


def understand(question, context=None):
    ctx = dict(empty_context())
    if context:
        ctx.update(context)
    q = question.replace("\u2019", "'")
    text_us = q.replace("_", " ")
    toks = _tokenize(text_us)
    lw = [t[0].lower() for t in toks]
    lset = set(lw)

    product, product_words = _find_product(text_us)
    dates = parse_dates(text_us)

    metrics = []
    for w in lw:
        if w in METRIC_MAP and METRIC_MAP[w] not in metrics:
            metrics.append(METRIC_MAP[w])
    has_weather = any(w in WEATHER_WORDS for w in lw)

    resolved_stores, unresolved_words = _resolve_stores(
        toks, product_words, bool(metrics), has_weather, dates["present"])
    store_names = []
    for s, _c, _k in resolved_stores:
        if s not in store_names:
            store_names.append(s)
    named_store = bool(store_names) or bool(unresolved_words)

    # ---------------- intent, in the fixed order
    # rule 1: override / prohibited action
    prohibited = bool(lset & OVERRIDE_WORDS) or bool(re.search(r"\bplace\s+an\s+order\b", text_us, re.I))
    if not prohibited:
        for i, w in enumerate(lw):
            if w in ("order", "reorder") and _is_imperative_order(lw, text_us, i):
                prohibited = True
            elif w in ("order", "reorder") and i > 0 and re.search(r",\s*" + w + r"\b", text_us, re.I) \
                    and not (i + 1 < len(lw) and lw[i + 1] in ("threshold", "thresholds", "level", "levels", "point", "points")):
                prohibited = True
    unsupported = bool(lset & UNSUPPORTED_WORDS) or any(
        lw[i] == "per" and i + 1 < len(lw) and lw[i + 1] in ("footfall", "footfalls", "visitor", "visitors")
        for i in range(len(lw)))
    has_target_word = bool(lset & {"target", "targets"})
    tva_phrase = ("achievement" in lset or "achievements" in lset
                  or re.search(r"\bperformance\s+band\b", text_us, re.I) is not None
                  or re.search(r"\bfall\s+short\b", text_us, re.I) is not None)

    if prohibited:
        intent = "out_of_scope"
    elif unsupported:
        intent = "unsupported_metric"
    elif lset & DIAGNOSTIC_WORDS:
        intent = "diagnostic"
    elif product or (lset & INVENTORY_WORDS):
        intent = "inventory"
    elif lset & FEEDBACK_WORDS or re.search(r"\bcustomers?\s+(?:say|says|saying)\b", text_us, re.I):
        intent = "feedback"
    elif (has_target_word and (lset & TARGET_PARTNERS)) or tva_phrase:
        intent = "target_vs_actual"
    elif (lset & COMPARISON_WORDS) and not named_store:
        intent = "comparison"
    elif metrics:
        intent = "lookup"
    elif has_weather:
        intent = "weather"
    elif named_store or dates["present"]:
        intent = "target_vs_actual" if ctx.get("tva") else "lookup"
    else:
        intent = "out_of_scope"

    base = {"intent": intent, "store": None, "metric": None, "date": None, "date_range": None,
            "product": None, "weather": has_weather, "confidence": 1.0, "missing": [],
            "unresolved": {"store": None, "date": None}, "ambiguous": None, "order": "desc",
            "store_confidence": None, "context_update": None}

    if intent in ("unsupported_metric", "out_of_scope", "diagnostic"):
        return base

    # ---------------- entity use per intent
    uses_store = intent in ("lookup", "target_vs_actual", "feedback", "weather", "inventory")
    store_required = intent in ("lookup", "target_vs_actual", "feedback", "weather")
    uses_metric = intent in ("lookup", "comparison")
    uses_date = intent in ("lookup", "target_vs_actual", "comparison", "weather")
    single_date_only = intent in ("target_vs_actual", "weather")
    uses_product = intent == "inventory"

    confs = []
    # --- store
    store = None
    store_conf = None
    ambiguous = None
    unresolved_store = None
    if unresolved_words:
        unresolved_store = ", ".join(unresolved_words)
        confs.append(UNRESOLVED_CONF)
    if uses_store and not unresolved_store:
        if len(store_names) > 1:
            ambiguous = {"kind": "store", "options": store_names}
            confs.append(UNRESOLVED_CONF)
        elif len(store_names) == 1:
            store = store_names[0]
            store_conf = min(c for s, c, k in resolved_stores if s == store)
            confs.append(store_conf)
        elif store_required and ctx.get("store"):
            store = ctx["store"]
            store_conf = 1.0
            confs.append(1.0)
        elif store_required:
            confs.append(UNRESOLVED_CONF)
    base["store_confidence"] = store_conf

    # --- metric
    metric = None
    if uses_metric:
        if len(metrics) > 1:
            ambiguous = ambiguous or {"kind": "metric", "options": metrics}
            confs.append(UNRESOLVED_CONF)
        elif len(metrics) == 1:
            metric = metrics[0]
            confs.append(1.0)
        elif ctx.get("metric"):
            metric = ctx["metric"]
            confs.append(1.0)
        else:
            confs.append(UNRESOLVED_CONF)

    # --- date
    date_single, date_range, unresolved_date = None, None, None
    if uses_date:
        if dates["unresolved"]:
            unresolved_date = ", ".join(dates["unresolved"])
        elif dates["single"]:
            date_single = dates["single"].isoformat()
        elif dates["range"]:
            if single_date_only:
                unresolved_date = "a date range (this question needs one date)"
            else:
                date_range = (dates["range"][0].isoformat(), dates["range"][1].isoformat())
        elif ctx.get("date"):
            date_single = ctx["date"]
        elif ctx.get("range"):
            if single_date_only:
                unresolved_date = "a date range (this question needs one date)"
            else:
                date_range = tuple(ctx["range"])
        if unresolved_date:
            confs.append(UNRESOLVED_CONF)
        elif date_single or date_range:
            confs.append(1.0)
        else:
            confs.append(UNRESOLVED_CONF)

    # --- product
    prod = None
    if uses_product:
        if product:
            prod = product
            confs.append(1.0)
        elif ctx.get("product"):
            prod = ctx["product"]
            confs.append(1.0)
        else:
            confs.append(UNRESOLVED_CONF)

    if ambiguous:
        confs = [c for c in confs if c >= UNRESOLVED_CONF]

    missing = []
    if store_required and store is None and not unresolved_store and not ambiguous:
        missing.append("store")
    if uses_metric and metric is None and not ambiguous:
        missing.append("metric")
    if uses_date and date_single is None and date_range is None and not unresolved_date:
        missing.append("date")
    if uses_product and prod is None:
        missing.append("product")

    # --- comparison direction
    order = "desc"
    if intent == "comparison":
        for w in lw:
            if w in ("highest", "lowest", "best", "worst"):
                if w == "highest":
                    order = "desc"
                elif w == "lowest":
                    order = "asc"
                elif w == "best":
                    order = "asc" if metric == "stockout_hours" else "desc"
                else:
                    order = "desc" if metric == "stockout_hours" else "asc"
                break

    confidence = min(confs) if confs else 1.0
    base.update({
        "store": store, "metric": metric if intent != "target_vs_actual" else None,
        "date": date_single, "date_range": date_range, "product": prod,
        "confidence": round(confidence, 2), "missing": missing,
        "unresolved": {"store": unresolved_store, "date": unresolved_date},
        "ambiguous": ambiguous, "order": order,
    })

    # ---------------- context update: used entities that were resolved
    new_ctx = dict(ctx)
    if not ambiguous:
        if uses_store and store and not unresolved_store:
            new_ctx["store"] = store
        if uses_metric and metric:
            new_ctx["metric"] = metric
        if uses_date and not unresolved_date:
            if date_single:
                new_ctx["date"], new_ctx["range"] = date_single, None
            elif date_range:
                new_ctx["range"], new_ctx["date"] = date_range, None
        if uses_product and prod:
            new_ctx["product"] = prod
    else:
        # an ambiguous pair is never stored; other resolved entities still are
        if uses_metric and metric:
            new_ctx["metric"] = metric
        if uses_date and not unresolved_date:
            if date_single:
                new_ctx["date"], new_ctx["range"] = date_single, None
            elif date_range:
                new_ctx["range"], new_ctx["date"] = date_range, None
        if uses_product and prod:
            new_ctx["product"] = prod
    new_ctx["tva"] = intent == "target_vs_actual"
    base["context_update"] = new_ctx
    return base
