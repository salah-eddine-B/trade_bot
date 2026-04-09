import re
from statistics import median

_NUM = r'(\d{3,6}(?:\.\d+)?)'

def clean_text(text):
    text = re.sub(r'[@#]\S+', ' ', text)
    text = re.sub(r'[^\w\s\.\-/()]', ' ', text)
    return text.upper()

def detect_symbol(text):
    patterns = {
        "XAUUSD": r'(XAU\s*/?\s*USD|GOLD)',
        "EURUSD": r'(EUR\s*/?\s*USD)',
        "GBPUSD": r'(GBP\s*/?\s*USD)',
        "BTCUSD": r'(BTC\s*/?\s*USD|BITCOIN)',
    }
    for sym, pattern in patterns.items():
        if re.search(pattern, text):
            return sym
    return None

def extract_numbers(text):
    return [float(x) for x in re.findall(_NUM, text)]

def parse_signal(text):
    text = clean_text(text)

    symbol = detect_symbol(text)

    action = "BUY" if "BUY" in text else "SELL" if "SELL" in text else None

    # ✅ TP + TARGET support
    tps = [
        float(v) for v in re.findall(
            r'(?:TP|TARGET)\s*\d*\s*[:\-]?\s*\(?\s*' + _NUM,
            text
        )
    ]

    # SL
    sl_match = re.search(r'SL\s*[:\-]?\s*\(?\s*' + _NUM, text)
    sl = float(sl_match.group(1)) if sl_match else None

    # ENTRY
    entry = None

    range_match = re.search(rf'{_NUM}\s*[/\-~]\s*{_NUM}', text)
    if range_match:
        entry = (float(range_match.group(1)) + float(range_match.group(2))) / 2

    if entry is None:
        after_action = re.search(r'(BUY|SELL)\s+' + _NUM, text)
        if after_action:
            entry = float(after_action.group(2))

    if entry is None:
        nums = extract_numbers(text)
        known = set(tps)
        if sl:
            known.add(sl)
        candidates = [n for n in nums if n not in known]
        if candidates:
            entry = sorted(candidates)[len(candidates)//2]

    return {
        "symbol": symbol,
        "action": action,
        "entry": entry,
        "tps": tps,
        "sl": sl,
        "valid": symbol is not None and action is not None and entry is not None
    }