import re

def parse_signal(text):
    text = text.upper()

    # ✅ SYMBOL
    symbol_match = re.search(r'(XAUUSD|EURUSD|GBPUSD)', text)
    symbol = symbol_match.group(0) if symbol_match else None

    # ✅ ACTION
    action = "BUY" if "BUY" in text else "SELL"

    # ✅ ENTRY (range like 4410/4406)
    entry_match = re.search(r'(\d+\.?\d*)/(\d+\.?\d*)', text)
    if entry_match:
        entry1 = float(entry_match.group(1))
        entry2 = float(entry_match.group(2))
        entry = (entry1 + entry2) / 2
    else:
        entry = None

    # ✅ TAKE PROFITS (multiple)
    tps = re.findall(r'TP\s*(\d+\.?\d*)', text)
    tps = [float(tp) for tp in tps]

    # ✅ STOP LOSS (if exists)
    sl_match = re.search(r'SL\s*(\d+\.?\d*)', text)
    sl = float(sl_match.group(1)) if sl_match else None

    # 🔥 AUTO SL (Option B)
    if sl is None and entry is not None:
        if symbol == "XAUUSD":
            distance = 10  # gold SL distance
        else:
            distance = 0.005  # forex default

        if action == "BUY":
            sl = entry - distance
        else:
            sl = entry + distance

    return {
        "symbol": symbol,
        "action": action,
        "entry": entry,
        "tps": tps,
        "sl": sl
    }