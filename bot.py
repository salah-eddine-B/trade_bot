from telethon import TelegramClient, events
import MetaTrader5 as mt5
from parser import parse_signal
from monitor import register_commands, position_monitor, ADMIN_ID
import json
import logging
import asyncio
from datetime import datetime

# =========================
# LOGGING SETUP
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# =========================
# TELEGRAM CONFIG
# =========================
api_id   = 38573702
api_hash = "d9d60a5689656529b3e23a21d3553a65"
CHANNEL_ID = -1001402220998

# =========================
# TRADING CONFIG
# =========================
LOT = 0.01

# =========================
# INIT MT5
# =========================
if not mt5.initialize():
    log.critical("MT5 initialization failed — exiting")
    quit()

log.info("MT5 connected")

client = TelegramClient("session", api_id, api_hash)

# =========================
# SYMBOL MAPPER (🔥 FIX)
# =========================
def map_symbol(symbol):
    symbols = mt5.symbols_get()
    for s in symbols:
        if symbol in s.name:
            return s.name
    return None

# =========================
# DUPLICATE PROTECTION
# =========================
last_message = None

# =========================
# SEND TRADE
# =========================
def send_trade(data):
    try:
        symbol_raw = data["symbol"]
        symbol = map_symbol(symbol_raw)

        if not symbol:
            log.error(f"No matching broker symbol for {symbol_raw}")
            return

        action = data["action"]
        tps = data["tps"]
        sl = data["sl"]

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            log.error(f"Symbol {symbol} not available")
            return

        price = tick.ask if action == "BUY" else tick.bid

        tp = tps[0] if tps else None

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

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            log.info(f"Trade executed | {symbol} {action} | ticket={result.order}")
            log_trade(symbol, action, price, sl, tp, LOT, result.order)
        else:
            log.error(f"Trade failed | retcode={result.retcode} | {result.comment}")

    except Exception as e:
        log.exception(f"send_trade crashed: {e}")

# =========================
# LOG TRADE
# =========================
def log_trade(symbol, action, entry, sl, tp, lot, ticket=None):
    try:
        trade_record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "action": action,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "lot": lot,
            "ticket": ticket,
        }

        try:
            with open("trades.json", "r") as f:
                trades = json.load(f)
        except:
            trades = []

        trades.append(trade_record)

        with open("trades.json", "w") as f:
            json.dump(trades, f, indent=4)

        log.info("Trade logged")

    except Exception as e:
        log.exception(f"log_trade failed: {e}")

# =========================
# TELEGRAM HANDLER
# =========================
@client.on(events.NewMessage(chats=CHANNEL_ID))
async def handler(event):
    global last_message

    try:
        message = event.message.message

        # 🚫 duplicate protection
        if message == last_message:
            log.warning("Duplicate message skipped")
            return

        last_message = message

        log.info(f"New message:\n{message}")

        data = parse_signal(message)

        log.info(f"Parsed signal: {data}")

        # basic safety (only required fields)
        if not data["symbol"] or not data["action"] or not data["entry"]:
            log.warning("Invalid signal — missing essential fields")
            return

        send_trade(data)

    except Exception as e:
        log.exception(f"Handler crashed: {e}")

# =========================
# MAIN
# =========================
async def main():
    await client.start()
    register_commands(client)

    log.info("Bot is running...")

    if ADMIN_ID:
        asyncio.create_task(position_monitor(client, ADMIN_ID))

    await client.run_until_disconnected()

asyncio.run(main())