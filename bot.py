from telethon import TelegramClient, events
import MetaTrader5 as mt5
from parser import parse_signal
import json
import logging
from datetime import datetime

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# =========================
# CONFIG
# =========================
api_id   = 38573702
api_hash = "d9d60a5689656529b3e23a21d3553a65"
CHANNEL_ID = -1001402220998
LOT = 0.01

# =========================
# MT5 INIT
# =========================
if not mt5.initialize():
    log.critical("MT5 init failed")
    quit()

log.info("MT5 connected")

client = TelegramClient("session", api_id, api_hash)

# =========================
# SYMBOL FIX
# =========================
def map_symbol(symbol):
    for s in mt5.symbols_get():
        if symbol in s.name:
            return s.name
    return None

# =========================
# DUPLICATE PROTECTION
# =========================
last_message = None

# =========================
# TRADE EXECUTION
# =========================
def send_trade(data):
    try:
        symbol = map_symbol(data["symbol"])
        if not symbol:
            log.error("Symbol not found in broker")
            return

        action = data["action"]
        tps = data["tps"]
        sl = data["sl"]

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            log.error("Symbol not available")
            return

        price = tick.ask if action == "BUY" else tick.bid

        # ✅ TP fallback
        if not tps:
            log.warning("No TP found — using default TP")
            tp = price + 5 if action == "BUY" else price - 5
        else:
            tp = tps[0]

        order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": LOT,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 999999,
            "comment": "AI Bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        # ✅ FIX crash
        if result is None:
            log.error("MT5 returned None (AutoTrading OFF or market closed)")
            return

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            log.info(f"Trade executed | ticket={result.order}")
            log_trade(symbol, action, price, sl, tp, LOT, result.order)
        else:
            log.error(f"Trade failed | {result.retcode} | {result.comment}")

    except Exception as e:
        log.exception(f"send_trade error: {e}")

# =========================
# LOGGING TRADES
# =========================
def log_trade(symbol, action, entry, sl, tp, lot, ticket):
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "action": action,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "lot": lot,
        "ticket": ticket
    }

    try:
        with open("trades.json", "r") as f:
            data = json.load(f)
    except:
        data = []

    data.append(record)

    with open("trades.json", "w") as f:
        json.dump(data, f, indent=4)

# =========================
# TELEGRAM HANDLER
# =========================
@client.on(events.NewMessage(chats=CHANNEL_ID))
async def handler(event):
    global last_message

    msg = event.message.message

    if msg == last_message:
        log.warning("Duplicate skipped")
        return

    last_message = msg

    log.info(f"New message:\n{msg}")

    data = parse_signal(msg)
    log.info(f"Parsed: {data}")

    if not data["valid"]:
        log.warning("Invalid signal")
        return

    send_trade(data)

# =========================
# START
# =========================
client.start()
log.info("Bot running...")
client.run_until_disconnected()