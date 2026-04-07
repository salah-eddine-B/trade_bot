from parser import parse_signal


signal = "XAUUSD BUY 4400/4405"

result = parse_signal(signal)

if not result["symbol"] or not result["entry"]:
    print("❌ Invalid signal")
else:
    print("✅ Valid signal:", result)