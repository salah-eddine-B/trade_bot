import re


# All numbers that appear in a signal, tagged by their role
_NUM = r'(\d{3,6}(?:\.\d+)?)'   # 3-6 digit price, optional decimals


def _extract_numbers(text: str) -> list[float]:
    """Return every price-like number in the text, in order."""
    return [float(x) for x in re.findall(r'\d{3,6}(?:\.\d+)?', text)]


def parse_signal(text: str) -> dict:
    upper = text.upper()

    # ── Symbol ────────────────────────────────────────────────────────────────
    sym_match = re.search(r'(XAUUSD|GOLD|EURUSD|GBPUSD|BTCUSD|US30|NAS100)', upper)
    raw_sym   = sym_match.group(1) if sym_match else None
    symbol    = "XAUUSD" if raw_sym in ("XAUUSD", "GOLD") else raw_sym

    # ── Action ────────────────────────────────────────────────────────────────
    action = "BUY" if "BUY" in upper else "SELL" if "SELL" in upper else None

    # ── Take Profits — grab first before entry so we can exclude them ─────────
    # Matches: TP1 3210, TP: 3210, TP 3210, TP3210
    tps = [float(v) for v in re.findall(r'TP\s*\d*\s*[:\-]?\s*' + _NUM, upper)]

    # ── Stop Loss ─────────────────────────────────────────────────────────────
    sl_match = re.search(r'SL\s*[:\-]?\s*' + _NUM, upper)
    sl = float(sl_match.group(1)) if sl_match else None

    # ── Entry ─────────────────────────────────────────────────────────────────
    entry = None

    # 1. Explicit range:  4702/4706  or  4702 - 4706  or  4702~4706
    range_match = re.search(r'(\d{3,6}(?:\.\d+)?)\s*[/\-~]\s*(\d{3,6}(?:\.\d+)?)', upper)
    if range_match:
        a, b = float(range_match.group(1)), float(range_match.group(2))
        # make sure it's not a TP or SL value
        if a not in tps and b not in tps and a != sl and b != sl:
            entry = (a + b) / 2

    # 2. Keyword:  ENTRY 4752  /  @ 4752  /  AT 4752
    if entry is None:
        kw = re.search(r'(?:ENTRY|@|AT)\s*[:\-]?\s*' + _NUM, upper)
        if kw:
            entry = float(kw.group(1))

    # 3. Number right after BUY/SELL:  BUY 4752  /  SELL 3210.50
    if entry is None:
        after_action = re.search(r'(?:BUY|SELL)\s+' + _NUM, upper)
        if after_action:
            candidate = float(after_action.group(1))
            if candidate not in tps and candidate != sl:
                entry = candidate

    # 4. Smart fallback — collect all numbers, remove known TP/SL values,
    #    pick the one closest to the median of all prices (most "central" price)
    if entry is None:
        all_nums = _extract_numbers(upper)
        known    = set(tps) | ({sl} if sl else set())
        candidates = [n for n in all_nums if n not in known]
        if candidates:
            median = sorted(candidates)[len(candidates) // 2]
            entry  = min(candidates, key=lambda x: abs(x - median))

    # ── Auto SL if missing ────────────────────────────────────────────────────
    if sl is None and entry is not None:
        distance = 10.0 if symbol == "XAUUSD" else 0.005
        sl = round(entry - distance if action == "BUY" else entry + distance, 5)

    return {
        "symbol":     symbol,
        "action":     action,
        "entry":      entry,
        "tps":        tps,
        "sl":         sl,
        "sl_missing": sl_match is None,
    }
