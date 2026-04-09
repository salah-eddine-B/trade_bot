from telethon import TelegramClient, events
import MetaTrader5 as mt5
from parser import parse_signal
from monitor import register_commands, position_monitor, ADMIN_ID
import json
import logging
import asyncio
from datetime import datetime

# =========================
# 📝 LOGGING SETUP
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
# 🔐 CONFIG
# =========================
api_id     = 38573702
api_hash   = "d9d60a5689656529b3e23a21d3553a65"
CHANNEL_ID = -1001402220998
LOT        = 0.01
RISK_PERCENT = 0.13   # 13% of balance → ~8 USD on a 60 USD account

# =========================
# 🚀 MT5 INIT
# =========================
if not mt5.initialize():
    log.critical("MT5 initialization failed — exiting")
    quit()

log.info("MT5 connected")

# =========================
# 🤖 TELEGRAM CLIENT
# =========================
client = TelegramClient("session", api_id, api_hash)

# =========================
# 🔍 SYMBOL RESOLVER
# =========================
def map_symbol(symbol):
    """Find the exact broker symbol name (e.g. 'XAUUSD' → 'XAUUSDm')."""
    try:
        for s in mt5.symbols_get():
            if symbol in s.name:
                return s.name
    except Exception as e:
        log.warning(f"map_symbol error: {e}")
    return None

# =========================
# 💵 ACCOUNT HELPERS
# =========================
def get_account_info():
    info = mt5.account_info()
    if not info:
        return None
    return {
        "balance":      info.balance,
        "equity":       info.equity,
        "margin":       info.margin,
        "free_margin":  info.margin_free,
        "profit":       info.profit,
        "currency":     info.currency,
        "leverage":     info.leverage,
        "login":        info.login,
    }

def calc_sl_distance(symbol: str) -> float:
    """
    Returns SL distance in price points so max loss = RISK_PERCENT * balance.
    Falls back to 15 pts if anything fails.
    """
    try:
        acc = get_account_info()
        if not acc:
            raise ValueError("No account info")

        risk_usd = acc["balance"] * RISK_PERCENT

        sym_info = mt5.symbol_info(symbol)
        if not sym_info:
            raise ValueError(f"No symbol info for {symbol}")

        tick_value = sym_info.trade_tick_value
        tick_size  = sym_info.trade_tick_size

        if tick_value <= 0 or tick_size <= 0:
            raise ValueError("Invalid tick data")

        sl_distance = (risk_usd / (tick_value * LOT)) * tick_size
        log.info(
            f"SL calc: balance={acc['balance']:.2f} {acc['currency']} | "
            f"risk={risk_usd:.2f} USD | sl_distance={sl_distance:.2f} pts"
        )
        return round(sl_distance, 2)

    except Exception as e:
        log.warning(f"SL calc failed ({e}) — using default 15 pts")
        return 15.0

# =========================
# 📊 SEND TRADE
# =========================
def send_trade(data):
    try:
        raw_symbol = data["symbol"]
        symbol = map_symbol(raw_symbol)
        if not symbol:
            log.error(f"Symbol '{raw_symbol}' not found in broker")
            return

        action = data["action"]
        tps    = data["tps"]
        signal_sl = data.get("sl")

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            log.error(f"No tick data for {symbol}")
            return

        live_price = tick.ask if action == "BUY" else tick.bid

        # ── SL: balance-based, capped by signal SL if provided ──────────────
        sl_distance = calc_sl_distance(symbol)
        if signal_sl is not None and data.get("entry"):
            signal_sl_dist = abs(data["entry"] - signal_sl)
            if signal_sl_dist > 0:
                sl_distance = min(sl_distance, signal_sl_dist)

        sl = round(live_price - sl_distance, 2) if action == "BUY" else round(live_price + sl_distance, 2)

        # ── TPs: validate direction ──────────────────────────────────────────
        valid_tps = []
        for tp_val in tps:
            dist = abs(tp_val - (data["entry"] or live_price))
            if action == "BUY":
                tp = round(live_price + dist, 2)
                if tp > live_price and tp > sl:
                    valid_tps.append(tp)
            else:
                tp = round(live_price - dist, 2)
                if tp < live_price and tp < sl:
                    valid_tps.append(tp)

        # ── TP fallback ──────────────────────────────────────────────────────
        if not valid_tps:
            default_tp = round(live_price + 10, 2) if action == "BUY" else round(live_price - 10, 2)
            log.warning(f"No valid TPs — using default TP {default_tp}")
            valid_tps = [default_tp]

        # ── Lot split ────────────────────────────────────────────────────────
        sym_info = mt5.symbol_info(symbol)
        min_lot  = sym_info.volume_min  if sym_info else 0.01
        lot_step = sym_info.volume_step if sym_info else 0.01
        per_lot  = max(min_lot, round(LOT / len(valid_tps), 2))
        per_lot  = round(round(per_lot / lot_step) * lot_step, 2)

        log.info(f"Live: {live_price} | SL: {sl} | TPs: {valid_tps} | Lot/trade: {per_lot}")

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

            if result is None:
                log.error("MT5 returned None — AutoTrading may be OFF or market closed")
                continue

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                log.info(f"Trade {i+1}/{len(valid_tps)} opened | TP={tp} | ticket={result.order}")
                log_trade(symbol, action, live_price, sl, tp, per_lot, result.order)
            else:
                log.error(f"Trade {i+1} failed | retcode={result.retcode} | {result.comment}")

    except Exception as e:
        log.exception(f"send_trade crashed: {e}")

# =========================
# 💾 LOG TRADE
# =========================
def log_trade(symbol, action, entry, sl, tp, lot, ticket):
    try:
        record = {
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
            with open("trades.json", "r", encoding="utf-8") as f:
                trades = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            trades = []

        trades.append(record)

        with open("trades.json", "w", encoding="utf-8") as f:
            json.dump(trades, f, indent=4)

        log.info(f"Trade logged | ticket={ticket}")
    except Exception as e:
        log.exception(f"log_trade failed: {e}")

# =========================
# 📩 SIGNAL HANDLER
# =========================
last_message = None

@client.on(events.NewMessage(chats=CHANNEL_ID))
async def handler(event):
    global last_message
    try:
        msg = event.message.message

        if not msg or not msg.strip():
            return

        if msg == last_message:
            log.warning("Duplicate message — skipped")
            return
        last_message = msg

        log.info(f"New message:\n{msg}")

        data = parse_signal(msg)
        log.info(f"Parsed: {data}")

        if not data.get("valid"):
            log.warning(
                f"Invalid signal — missing fields: "
                f"symbol={data.get('symbol')} action={data.get('action')} entry={data.get('entry')}"
            )
            return

        send_trade(data)

    except Exception as e:
        log.exception(f"Handler crashed: {e}")

# =========================
# ▶️ MAIN
# =========================
async def main():
    try:
        await client.start()
        register_commands(client)
        log.info("Bot is running...")

        if ADMIN_ID:
            asyncio.create_task(position_monitor(client, ADMIN_ID))

            acc = get_account_info()
            if acc:
                startup_msg = (
                    f"🤖 *Bot started*\n\n"
                    f"💰 *Account #{acc['login']}*\n"
                    f"  Balance:     `{acc['balance']:.2f} {acc['currency']}`\n"
                    f"  Equity:      `{acc['equity']:.2f} {acc['currency']}`\n"
                    f"  Free Margin: `{acc['free_margin']:.2f} {acc['currency']}`\n"
                    f"  Leverage:    `1:{acc['leverage']}`\n"
                    f"  Open P&L:    `{acc['profit']:+.2f} {acc['currency']}`\n\n"
                    f"⚙️ Risk per trade: `{RISK_PERCENT*100:.0f}%` "
                    f"≈ `{acc['balance']*RISK_PERCENT:.2f} {acc['currency']}`\n"
                    f"📡 Monitoring positions every {POLL_INTERVAL}s"
                )
            else:
                startup_msg = "🤖 Bot started and monitoring positions."

            try:
                await client.send_message(ADMIN_ID, startup_msg, parse_mode="markdown")
            except Exception:
                await client.send_message("me", startup_msg, parse_mode="markdown")

            log.info(f"Position monitor active → notifying {ADMIN_ID}")
        else:
            log.warning("ADMIN_ID not set — position monitor disabled")

        await client.run_until_disconnected()

    except Exception as e:
        log.exception(f"main() crashed: {e}")

# reference POLL_INTERVAL from monitor
from monitor import POLL_INTERVAL

asyncio.run(main())
