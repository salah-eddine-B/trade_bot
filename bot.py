from telethon import TelegramClient, events
import MetaTrader5 as mt5
from parser import parse_signal
from monitor import register_commands, position_monitor, ADMIN_ID
import json
import re
import logging
import asyncio
from datetime import datetime

# =========================
# � LOGGING SETUP
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
# �🔐 Telegram config
# =========================
api_id   = 38573702
api_hash = "d9d60a5689656529b3e23a21d3553a65"
CHANNEL_ID = -1001402220998

# =========================
# 💰 TRADING CONFIG
# =========================
LOT = 0.01
RISK_PERCENT = 0.13   # 13% of balance → ~8 USD on a 60 USD account

# =========================
# 🚀 INIT MT5
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
# 💵 ACCOUNT HELPERS
# =========================
def get_account_info():
    info = mt5.account_info()
    if not info:
        return None
    return {
        "balance":  info.balance,
        "equity":   info.equity,
        "margin":   info.margin,
        "free_margin": info.margin_free,
        "profit":   info.profit,
        "currency": info.currency,
        "leverage": info.leverage,
        "login":    info.login,
    }

def calc_sl_distance_from_balance(symbol: str) -> float:
    """
    Calculates SL distance in price points so that the max loss
    equals RISK_PERCENT of the current account balance.
    Falls back to a safe default if anything fails.
    """
    try:
        acc = get_account_info()
        if not acc:
            raise ValueError("No account info")

        risk_usd = acc["balance"] * RISK_PERCENT   # e.g. 60 * 0.13 ≈ 7.8 USD

        sym_info = mt5.symbol_info(symbol)
        if not sym_info:
            raise ValueError(f"No symbol info for {symbol}")

        # tick_value = profit per 1 lot per 1 tick move
        tick_value = sym_info.trade_tick_value   # USD per lot per tick
        tick_size  = sym_info.trade_tick_size

        if tick_value <= 0 or tick_size <= 0:
            raise ValueError("Invalid tick data")

        # risk_usd = (sl_distance / tick_size) * tick_value * lot
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
# 📊 SEND TRADE TO MT5
# =========================
def send_trade(data):
    try:
        symbol    = data["symbol"]
        action    = data["action"]
        tps       = data["tps"]
        signal_entry = data["entry"]
        signal_sl    = data.get("sl")
        sl_missing   = data.get("sl_missing", signal_sl is None)

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            log.error(f"Symbol {symbol} not available")
            return

        live_price = tick.ask if action == "BUY" else tick.bid

        # ── Resolve SL ──────────────────────────────────────────────────────
        sl_distance = calc_sl_distance_from_balance(symbol)

        if not sl_missing and signal_sl is not None:
            # Use signal's SL distance but anchored to live price
            signal_sl_distance = abs(signal_entry - signal_sl)
            # take the smaller of the two (safer)
            sl_distance = min(sl_distance, signal_sl_distance) if signal_sl_distance > 0 else sl_distance

        sl = round(live_price - sl_distance, 2) if action == "BUY" else round(live_price + sl_distance, 2)

        if sl_missing:
            log.warning(f"SL missing in signal — auto SL set to {sl} (distance={sl_distance} pts)")

        # ── Validate TPs ────────────────────────────────────────────────────
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
            log.error("No valid TPs after adjustment — trade aborted")
            return

        # ── Split lot across TPs ─────────────────────────────────────────────
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

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                log.info(f"Trade {i+1}/{len(valid_tps)} opened | TP={tp} | ticket={result.order}")
                log_trade(symbol=symbol, action=action, entry=live_price,
                          sl=sl, tp=tp, lot=per_lot, ticket=result.order)
            else:
                log.error(f"Trade {i+1} failed | retcode={result.retcode} | {result.comment}")

    except Exception as e:
        log.exception(f"send_trade crashed: {e}")

# =========================
# 💾 LOG TRADES
# =========================
def log_trade(symbol, action, entry, sl, tp, lot, ticket=None):
    try:
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

        log.info(f"Trade logged | ticket={ticket}")
    except Exception as e:
        log.exception(f"log_trade failed: {e}")

# =========================
# 📩 TELEGRAM HANDLER
# =========================
@client.on(events.NewMessage)
async def handler(event):
    try:
        message = event.message.message
        log.info(f"New message received:\n{message}")

        data = parse_signal(message)

        if not data["symbol"] or not data["action"] or not data["entry"]:
            log.warning(f"Invalid signal — missing fields: symbol={data['symbol']} action={data['action']} entry={data['entry']}")
            return

        log.info(f"Parsed signal: {data}")
        send_trade(data)

    except Exception as e:
        log.exception(f"Handler crashed: {e}")

# =========================
# ▶️ START BOT
# =========================
async def main():
    try:
        await client.start()
        register_commands(client)
        log.info("Bot is running...")

        if ADMIN_ID:
            asyncio.create_task(position_monitor(client, ADMIN_ID))

            # Build startup message with account info
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
                    f"📡 Monitoring positions every {10}s"
                )
            else:
                startup_msg = "🤖 Bot started and monitoring positions."

            try:
                await client.send_message(ADMIN_ID, startup_msg, parse_mode="markdown")
            except Exception:
                await client.send_message("me", startup_msg, parse_mode="markdown")

            log.info(f"Position monitor active → notifying {ADMIN_ID}")
        else:
            log.warning("ADMIN_ID not set in monitor.py — position monitor disabled")

        await client.run_until_disconnected()

    except Exception as e:
        log.exception(f"main() crashed: {e}")

asyncio.run(main())
