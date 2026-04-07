import MetaTrader5 as mt5

mt5.initialize()

symbol = "XAUUSD"

info = mt5.symbol_info(symbol)

if info is None:
    print("❌ Symbol not found")
else:
    print("✅ Symbol found:", symbol)

mt5.shutdown()