"""
monitor.py — Remote control & live monitoring via Telegram
Commands you can send from your phone:
  /status    → all open positions with live P&L
  /price     → XAUUSD live bid/ask
  /trades    → last 10 trades from trades.json
  /close <ticket> → close a specific position
  /closeall  → close all open positions
"""

import asyncio
import json
import MetaTrader5 as mt5
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
# Your personal Telegram user ID (get it from @userinfobot on Telegram)
# Only messages from this ID will be accepted — security gate
ADMIN_ID = 5611063972  # ← SET THIS: e.g. 123456789

MONITOR_SYMBOLS = ["XAUUSD", "EURUSD", "GBPUSD"]  # symbols to watch for price cmd
POLL_INTERVAL   = 10   # seconds between position checks for auto-notify
TRADES_FILE     = "trades.json"


# ── Helpers ───────────────────────────────────────────────────────────────────
def _pnl_emoji(pnl):
    if pnl > 0:   return "🟢"
    if pnl < 0:   return "🔴"
    return "⚪"


def _fmt_position(pos):
    pnl   = pos.profit
    emoji = _pnl_emoji(pnl)
    sign  = "+" if pnl >= 0 else ""
    ptype = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
    return (
        f"{emoji} *{pos.symbol}* {ptype}\n"
        f"  Ticket: `{pos.ticket}`\n"
        f"  Open: `{pos.price_open:.2f}` → Now: `{pos.price_current:.2f}`\n"
        f"  SL: `{pos.sl:.2f}` | TP: `{pos.tp:.2f}`\n"
        f"  Lot: `{pos.volume}` | P&L: `{sign}{pnl:.2f} USD`\n"
        f"  Opened: {datetime.fromtimestamp(pos.time).strftime('%H:%M:%S')}"
    )


def close_position(pos) -> tuple[bool, str]:
    """Close a single position at market price."""
    tick = mt5.symbol_info_tick(pos.symbol)
    if not tick:
        return False, f"No tick data for {pos.symbol}"

    close_type  = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    close_price = tick.bid            if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       pos.symbol,
        "volume":       pos.volume,
        "type":         close_type,
        "position":     pos.ticket,
        "price":        close_price,
        "deviation":    20,
        "magic":        999999,
        "comment":      "Remote close",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        return True, f"Closed ticket {pos.ticket} | P&L: {pos.profit:+.2f} USD"
    return False, f"Failed retcode={result.retcode}: {result.comment}"


# ── Command handlers ──────────────────────────────────────────────────────────
async def cmd_status(event):
    positions = mt5.positions_get()
    if not positions:
        await event.respond("📭 No open positions right now.")
        return

    total_pnl = sum(p.profit for p in positions)
    sign      = "+" if total_pnl >= 0 else ""
    lines     = [f"📊 *{len(positions)} open position(s)* | Total P&L: `{sign}{total_pnl:.2f} USD`\n"]
    for pos in positions:
        lines.append(_fmt_position(pos))
    await event.respond("\n\n".join(lines), parse_mode="markdown")


async def cmd_price(event):
    lines = []
    for sym in MONITOR_SYMBOLS:
        tick = mt5.symbol_info_tick(sym)
        if tick:
            spread = round((tick.ask - tick.bid) * (10 if "JPY" not in sym else 100), 1)
            lines.append(f"*{sym}*  Bid: `{tick.bid:.2f}`  Ask: `{tick.ask:.2f}`  Spread: `{spread}`")
        else:
            lines.append(f"*{sym}*  ❌ unavailable")
    await event.respond("\n".join(lines), parse_mode="markdown")


async def cmd_trades(event):
    try:
        with open(TRADES_FILE) as f:
            trades = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        await event.respond("📭 No trades logged yet.")
        return

    recent = sorted(trades, key=lambda t: t.get("time", ""), reverse=True)[:10]
    lines  = [f"📋 *Last {len(recent)} trades:*\n"]
    for t in recent:
        action = t.get("action", "?")
        emoji  = "🟢" if action == "BUY" else "🔴"
        lines.append(
            f"{emoji} *{t.get('symbol')}* {action} | "
            f"Entry: `{t.get('entry', 0):.2f}` | "
            f"TP: `{t.get('tp', 0):.2f}` | "
            f"SL: `{t.get('sl', 0):.2f}` | "
            f"Lot: `{t.get('lot')}` | "
            f"`{t.get('time', '')}`"
        )
    await event.respond("\n".join(lines), parse_mode="markdown")


async def cmd_close(event):
    parts  = event.raw_text.strip().split()
    if len(parts) < 2 or not parts[1].isdigit():
        await event.respond("Usage: `/close <ticket>`", parse_mode="markdown")
        return

    ticket    = int(parts[1])
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        await event.respond(f"❌ No open position with ticket `{ticket}`", parse_mode="markdown")
        return

    ok, msg = close_position(positions[0])
    await event.respond(("✅ " if ok else "❌ ") + msg)


async def cmd_closeall(event):
    positions = mt5.positions_get()
    if not positions:
        await event.respond("📭 No open positions to close.")
        return

    await event.respond(f"⚠️ Closing {len(positions)} position(s)...")
    results = []
    for pos in positions:
        ok, msg = close_position(pos)
        results.append(("✅ " if ok else "❌ ") + msg)
    await event.respond("\n".join(results))


# ── Auto position monitor (notify on open/close) ──────────────────────────────
async def position_monitor(client, notify_id):
    """
    Polls MT5 every POLL_INTERVAL seconds.
    Sends a message when a position is opened or closed.
    """
    # resolve the entity once at startup so send_message always works
    try:
        me = await client.get_entity(notify_id)
    except Exception:
        me = "me"   # fallback: send to Saved Messages

    async def notify(msg):
        try:
            await client.send_message(me, msg, parse_mode="markdown")
        except Exception as e:
            print(f"⚠️ Notify failed: {e}")

    known = {p.ticket for p in (mt5.positions_get() or [])}
    print(f"👁️ Monitor started — tracking {len(known)} existing position(s)")

    while True:
        await asyncio.sleep(POLL_INTERVAL)
        try:
            current_positions = mt5.positions_get() or []
            current = {p.ticket: p for p in current_positions}
            current_ids = set(current.keys())

            # newly opened
            for ticket in current_ids - known:
                pos = current[ticket]
                msg = f"🚀 *New position opened!*\n\n{_fmt_position(pos)}"
                print(f"📤 Notifying: new position {ticket}")
                await notify(msg)

            # closed
            for ticket in known - current_ids:
                from datetime import datetime, timedelta
                now  = datetime.now()
                from_dt = now - timedelta(hours=24)
                history = mt5.history_deals_get(
                    int(from_dt.timestamp()),
                    int(now.timestamp()),
                    group="*"
                )
                # find the deal matching this position ticket
                deal = None
                if history:
                    matches = [d for d in history if d.position_id == ticket]
                    if matches:
                        deal = matches[-1]

                if deal:
                    pnl   = deal.profit
                    sign  = "+" if pnl >= 0 else ""
                    emoji = "🟢" if pnl >= 0 else "🔴"
                    msg   = (
                        f"{emoji} *Position closed*\n"
                        f"  Ticket: `{ticket}`\n"
                        f"  Symbol: `{deal.symbol}`\n"
                        f"  P&L: `{sign}{pnl:.2f} USD`\n"
                        f"  Time: {datetime.fromtimestamp(deal.time).strftime('%H:%M:%S')}"
                    )
                else:
                    msg = f"📕 Position `{ticket}` was closed."

                print(f"📤 Notifying: closed position {ticket}")
                await notify(msg)

            known = current_ids

        except Exception as e:
            print(f"⚠️ Monitor loop error: {e}")


# ── Register all commands on the client ──────────────────────────────────────
def register_commands(client):
    """Call this once after TelegramClient is created."""
    from telethon import events as tl_events

    def guard(handler):
        """Only accept commands from ADMIN_ID (including Saved Messages)."""
        async def wrapped(event):
            sender = event.sender_id
            # allow if sender is admin OR message is in your own Saved Messages
            if ADMIN_ID and sender != ADMIN_ID:
                try:
                    me = await client.get_me()
                    if sender != me.id:
                        return  # not you — ignore
                except Exception:
                    return
            await handler(event)
        return wrapped

    client.add_event_handler(guard(cmd_status),   tl_events.NewMessage(pattern=r"(?i)^/status"))
    client.add_event_handler(guard(cmd_price),    tl_events.NewMessage(pattern=r"(?i)^/price"))
    client.add_event_handler(guard(cmd_trades),   tl_events.NewMessage(pattern=r"(?i)^/trades"))
    client.add_event_handler(guard(cmd_close),    tl_events.NewMessage(pattern=r"(?i)^/close\b"))
    client.add_event_handler(guard(cmd_closeall), tl_events.NewMessage(pattern=r"(?i)^/closeall"))
