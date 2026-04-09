import re


_NUM = r'(\d{3,6}(?:\.\d+)?)'


def clean_text(text: str) -> str:
    """Remove noise like emojis, hashtags, usernames."""
    text = re.sub(r'[@#]\S+', ' ', text)   # remove @user, #tags
    text = re.sub(r'[^\w\s\.\-/]', ' ', text)  # remove emojis/symbols
    return text.upper()


def _extract_numbers(text: str):
    return [float(x) for x in re.findall(_NUM, text)]


def detect_symbol(text: str):
    patterns = {
        "XAUUSD": r'(XAU\s*/?\s*USD|GOLD)',
        "EURUSD": r'(EUR\s*/?\s*USD)',
        "GBPUSD": r'(GBP\s*/?\s*USD)',
        "BTCUSD": r'(BTC\s*/?\s*USD|BITCOIN)',
        "US30": r'US30',
        "NAS100": r'NAS100',
    }

    for sym, pattern in patterns.items():
        if re.search(pattern, text):
            return sym

    return None


def parse_signal(text: str) -> dict:
    text = clean_text(text)

    # =========================
    # SYMBOL
    # =========================
    symbol = detect_symbol(text)

    # =========================
    # ACTION
    # =========================
    action = None
    if "BUY" in text:
        action = "BUY"
    elif "SELL" in text:
        action = "SELL"

    # =========================
    # TAKE PROFITS
    # =========================
    tps = [float(v) for v in re.findall(r'TP\s*\d*\s*[:\-]?\s*' + _NUM, text)]

    # =========================
    # STOP LOSS
    # =========================
    sl_match = re.search(r'SL\s*[:\-]?\s*' + _NUM, text)
    sl = float(sl_match.group(1)) if sl_match else None

    # detect "SL INBOX"
    if "SL INBOX" in text or "SL @ " in text:
        sl = None

    # =========================
    # ENTRY
    # =========================
    entry = None

    # 1. Range
    range_match = re.search(rf'{_NUM}\s*[/\-~]\s*{_NUM}', text)
    if range_match:
        a, b = float(range_match.group(1)), float(range_match.group(2))
        if a not in tps and b not in tps:
            entry = (a + b) / 2

    # 2. ENTRY / AT / @
    if entry is None:
        kw = re.search(r'(ENTRY|@|AT)\s*[:\-]?\s*' + _NUM, text)
        if kw:
            entry = float(kw.group(2))

    # 3. After BUY/SELL
    if entry is None:
        after_action = re.search(r'(BUY|SELL)\s+' + _NUM, text)
        if after_action:
            candidate = float(after_action.group(2))
            if candidate not in tps:
                entry = candidate

    # 4. Smart fallback (improved)
    if entry is None:
        nums = _extract_numbers(text)
        known = set(tps)
        if sl:
            known.add(sl)

        candidates = [n for n in nums if n not in known]

        if candidates:
            # prefer numbers close to action keyword
            idx = text.find(action) if action else 0
            distances = [(abs(text.find(str(int(n))) - idx), n) for n in candidates]
            entry = sorted(distances)[0][1]

    # =========================
    # AUTO SL
    # =========================
    if sl is None and entry is not None:
        distance = 10.0 if symbol == "XAUUSD" else 0.005
        sl = round(entry - distance if action == "BUY" else entry + distance, 5)

    return {
        "symbol": symbol,
        "action": action,
        "entry": entry,
        "tps": tps,
        "sl": sl,
        "sl_missing": sl_match is None,
    }