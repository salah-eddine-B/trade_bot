import re
from statistics import median

_NUM = r'(\d{3,6}(?:\.\d+)?)'


# =========================
# CLEAN TEXT
# =========================
def clean_text(text):
    text = re.sub(r'[@#]\S+', ' ', text)
    text = re.sub(r'[^\w\s\.\-/]', ' ', text)
    return text.upper()


# =========================
# SYMBOL DETECTION
# =========================
def detect_symbol(text):
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


# =========================
# EXTRACT NUMBERS
# =========================
def extract_numbers(text):
    return [float(x) for x in re.findall(_NUM, text)]


# =========================
# SCORE ENTRY CANDIDATES
# =========================
def score_entry_candidates(text, numbers, tps, sl, action):
    candidates = []

    for n in numbers:
        score = 0

        # ❌ skip TP/SL
        if n in tps or n == sl:
            continue

        # ✔ closer to BUY/SELL keyword
        if action:
            idx_action = text.find(action)
            idx_num = text.find(str(int(n)))
            score += max(0, 50 - abs(idx_action - idx_num))

        # ✔ prefer middle values (not extreme TP)
        score += 50 - abs(n - median(numbers))

        candidates.append((score, n))

    if not candidates:
        return None

    # return highest score
    return sorted(candidates, reverse=True)[0][1]


# =========================
# MAIN PARSER
# =========================
def parse_signal(text):
    original_text = text
    text = clean_text(text)

    confidence = 0

    # =========================
    # SYMBOL
    # =========================
    symbol = detect_symbol(text)
    if symbol:
        confidence += 20

    # =========================
    # ACTION
    # =========================
    action = None
    if "BUY" in text:
        action = "BUY"
        confidence += 20
    elif "SELL" in text:
        action = "SELL"
        confidence += 20

    # =========================
    # TP
    # =========================
    tps = [float(v) for v in re.findall(r'TP\s*\d*\s*[:\-]?\s*' + _NUM, text)]
    if tps:
        confidence += 20

    # =========================
    # SL
    # =========================
    sl_match = re.search(r'SL\s*[:\-]?\s*' + _NUM, text)
    sl = float(sl_match.group(1)) if sl_match else None

    if sl:
        confidence += 10

    if "SL INBOX" in text:
        sl = None

    # =========================
    # ENTRY DETECTION
    # =========================
    entry = None

    # 1. Range
    range_match = re.search(rf'{_NUM}\s*[/\-~]\s*{_NUM}', text)
    if range_match:
        a, b = float(range_match.group(1)), float(range_match.group(2))
        entry = (a + b) / 2
        confidence += 20

    # 2. Keyword
    if entry is None:
        kw = re.search(r'(ENTRY|@|AT)\s*[:\-]?\s*' + _NUM, text)
        if kw:
            entry = float(kw.group(2))
            confidence += 15

    # 3. After action
    if entry is None:
        after_action = re.search(r'(BUY|SELL)\s+' + _NUM, text)
        if after_action:
            entry = float(after_action.group(2))
            confidence += 10

    # 4. AI scoring fallback
    if entry is None:
        nums = extract_numbers(text)
        entry = score_entry_candidates(text, nums, tps, sl, action)
        if entry:
            confidence += 10

    # =========================
    # AUTO SL
    # =========================
    if sl is None and entry:
        distance = 10.0 if symbol == "XAUUSD" else 0.005
        sl = entry - distance if action == "BUY" else entry + distance
        confidence += 5

    # =========================
    # FINAL VALIDATION
    # =========================
    is_valid = (
        symbol is not None and
        action is not None and
        entry is not None
    )

    return {
        "symbol": symbol,
        "action": action,
        "entry": entry,
        "tps": tps,
        "sl": sl,
        "confidence": confidence,
        "valid": is_valid
    }