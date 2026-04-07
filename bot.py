from telethon import TelegramClient, events
import MetaTrader5 as mt5
from parser import parse_signal
from monitor import register_commands, position_monitor, ADMIN_ID
import json
import re
from datetime import datetime

# 🔐 Telegram config
api_id = 38573702
api_hash = "d9d60a5689656529b3e23a21d3553a65"

# 📡 Channel ID (from earlier)
CHANNEL_ID = -1001402220998  


# =========================
# 💰 TRADING CONFIG
# =========================
LOT = 0.01

# =========================
# 🚀 INIT MT5
# =========================
if not mt5.initialize():
    print("❌ MT5 initialization failed")
    quit()

print("✅ MT5 connected")

# =========================
# 🤖 TELEGRAM CLIENT
# =========================
client = TelegramClient("session", api_id, api_hash)

# =========================
# 🧠 SIGNAL PARSER
# =========================
def parse_signal(text):
    upper = text.upper()

    # Symbol
    symbol = "XAUUSD" if "XAUUSD" in upper or "GOLD" in upper else None

    # Action
    action = "BUY" if "BUY" in upper else "SELL" if "SELL" in upper else None

    # Entry — range like 4702/4706 → average
    entry_match = re.search(r'(\d+\.?\d*)\s*/\s*(\d+\.?\d*)', upper)
    if entry_match:
        entry = (float(entry_match.group(1)) + float(entry_match.group(2))) / 2
    else:
        # single entry price
        single = re.search(r'(?:ENTRY|@|AT)?\s*(\d{3,5}\.?\d*)', upper)
        entry = float(single.group(1)) if single else None

    # Take Profits — all TP values in order
    tps = [float(v) for v in re.findall(r'TP\s*:?\s*(\d+\.?\d*)', upper)]

    # Stop Loss — explicit value or missing (SL INBOX / no SL)
    sl_match = re.search(r'SL\s*:?\s*(\d+\.?\d*)', upper)
    if sl_match:
        sl = float(sl_match.group(1))
    else:
        # SL not provided → auto-calculate: 15 pts beyond the worst entry side
        sl = None  # will be resolved in send_trade using live price

    return {
        "symbol": symbol,
        "action": action,
        "entry": entry,
        "tps": tps,
        "sl": sl,
        "sl_missing": sl is None,
    }

# =========================
# 📊 SEND TRADE TO MT5
# =========================
def send_trade(data):
    symbol = data["symbol"]
    action = data["action"]
    tps    = data["tps"]          # list of all TPs
    signal_entry  = data["entry"]
    signal_sl     = data["sl"]
    sl_missing    = data["sl_missing"]

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"❌ Symbol {symbol} not available")
        return

    live_price = tick.ask if action == "BUY" else tick.bid

    # ── Resolve SL ──────────────────────────────────────────────────────────
    if not sl_missing and signal_sl is not None:
        # Use signal's SL distance anchored to live price
        sl_distance = abs(signal_entry - signal_sl)
        sl = round(live_price - sl_distance, 2) if action == "BUY" else round(live_price + sl_distance, 2)
    else:
        # Auto SL: 15 pts from live price (safe default for XAUUSD)
        sl_distance = 15.0
        sl = round(live_price - sl_distance, 2) if action == "BUY" else round(live_price + sl_distance, 2)
        print(f"⚠️ SL missing in signal — auto SL set to {sl}")

    # ── Validate TPs against live price direction ────────────────────────────
    valid_tps = []
    for tp_val in tps:
        tp_distance = abs(tp_val - signal_entry) if signal_entry else abs(tp_val - live_price)
        if action == "BUY":
            tp = round(live_price + tp_distance, 2)
            if tp > live_price and tp > sl:
                valid_tps.append(tp)
        else:
            tp = round(live_price - tp_distance, 2)
            if tp < live_price and tp < sl:
                valid_tps.append(tp)

    if not valid_tps:
        print("❌ No valid TPs after adjustment")
        return

    # ── Split lot evenly across TPs ──────────────────────────────────────────
    sym_info = mt5.symbol_info(symbol)
    min_lot  = sym_info.volume_min  if sym_info else 0.01
    lot_step = sym_info.volume_step if sym_info else 0.01

    per_lot = max(min_lot, round(LOT / len(valid_tps), 2))
    # snap to lot_step
    per_lot = round(round(per_lot / lot_step) * lot_step, 2)

    print(f"📐 Live: {live_price} | SL: {sl} | TPs: {valid_tps} | Lot/trade: {per_lot}")

    order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL

    for i, tp in enumerate(valid_tps):
        request = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       symbol,
            "volume":       per_lot,
            "type":         order_type,
            "price":        live_price,
            "sl":           sl,
            "tp":           tp,
            "deviation":    20,
            "magic":        999999,
            "comment":      f"TG TP{i+1}",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"✅ Trade {i+1}/{len(valid_tps)} opened | TP={tp} | ticket={result.order}")
            log_trade(
                symbol=symbol,
                action=action,
                entry=live_price,
                sl=sl,
                tp=tp,
                lot=per_lot,
                ticket=result.order
            )
        else:
            print(f"❌ Trade {i+1} failed | retcode={result.retcode} | {result.comment}")

# =========================
# 💾 LOG TRADES
# =========================
def log_trade(symbol, action, entry, sl, tp, lot, ticket=None):
    trade_record = {
        "time":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "action": action,
        "entry":  entry,
        "sl":     sl,
        "tp":     tp,
        "lot":    lot,
        "ticket": ticket,
    }

    try:
        with open("trades.json", "r") as f:
            trades = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        trades = []

    trades.append(trade_record)

    with open("trades.json", "w") as f:
        json.dump(trades, f, indent=4)

    print(f"💾 Trade logged | ticket={ticket}")

# =========================
# 📩 TELEGRAM HANDLER
# =========================
@client.on(events.NewMessage)
async def handler(event):
    message = event.message.message
    print("\n📩 New message:\n", message)

    data = parse_signal(message)

    # 🛡️ validation
    if not data["symbol"] or not data["action"] or not data["entry"]:
        print("❌ Invalid signal")
        return

    print("✅ Parsed signal:", data)

    send_trade(data)

# =========================
# ▶️ START BOT
# =========================
import asyncio

async def main():
    await client.start()
    register_commands(client)   # ← remote control commands
    print("🤖 Bot is running...")

    # start position monitor if ADMIN_ID is set
    if ADMIN_ID:
        asyncio.create_task(position_monitor(client, ADMIN_ID))
        print(f"👁️ Position monitor active → notifying {ADMIN_ID}")
    else:
        print("⚠️ ADMIN_ID not set in monitor.py — position monitor disabled")

    await client.run_until_disconnected()

asyncio.run(main())