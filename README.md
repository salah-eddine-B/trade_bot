# Telegram → MT5 Auto Trading Bot

Automatically reads trading signals from a Telegram channel and executes them on MetaTrader 5. Includes a live dashboard and remote control from your phone.

---

## What it does

- Listens to a Telegram channel for trading signals
- Parses the signal (symbol, action, entry, SL, TPs)
- Opens trades on MT5 with proper lot sizing split across all TPs
- Auto-calculates SL if the signal doesn't include one
- Logs every trade to `trades.json`
- Lets you monitor and control trades remotely via Telegram commands
- Includes a web dashboard to view trade history

---

## Requirements

- Windows PC with **MetaTrader 5** installed and logged into a broker account
- Python 3.10+
- A Telegram account (not a bot token — your actual account)

---

## Installation

**1. Clone the project**

```bash
git clone https://github.com/yourname/trade-bot.git
cd trade-bot
```

**2. Install Python dependencies**

```bash
pip install telethon MetaTrader5
```

**3. Enable Algo Trading in MT5**

Open MT5 → Tools → Options → Expert Advisors → check **"Allow automated trading"**

Also make sure the symbol you trade (e.g. `XAUUSD`) is visible in your Market Watch panel.

---

## Configuration

Open `bot.py` and set these values at the top:

```python
api_id   = YOUR_API_ID       # from my.telegram.org
api_hash = "YOUR_API_HASH"   # from my.telegram.org
CHANNEL_ID = -100XXXXXXXXXX  # target channel ID
LOT = 0.01                   # base lot size per signal
```

### Getting your Telegram API credentials

1. Go to [https://my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Click **API development tools**
4. Create an app — copy `api_id` and `api_hash`

### Getting a channel ID

Run `get_channels.py` — it prints all channels you're a member of with their IDs:

```bash
python get_channels.py
```

### Setting up remote control (optional but recommended)

Open `monitor.py` and set your Telegram user ID:

```python
ADMIN_ID = 123456789  # your Telegram user ID
```

Get your ID by messaging [@userinfobot](https://t.me/userinfobot) on Telegram.

---

## Running the bot

```bash
python bot.py
```

The first time you run it, Telethon will ask for your phone number and a confirmation code to log in. After that it saves a `session.session` file and logs in automatically.

---

## Signal format

The bot understands signals in this format:

```
XAUUSD GOLD SELL 4702/4706
TP 4698 TP 4694 TP 4690 TP 4686 TP 4682 TP 4678
SL 4720
```

| Part | Description |
|---|---|
| `XAUUSD` or `GOLD` | Symbol (currently supports XAUUSD) |
| `BUY` / `SELL` | Trade direction |
| `4702/4706` | Entry range — bot averages it |
| `TP 4698 TP 4694 ...` | One trade opened per TP |
| `SL 4720` | Stop loss — auto-calculated if missing |

If SL is missing (`SL INBOX` or not present), the bot sets it automatically to 15 points from the live price.

---

## Remote control from your phone

Once `ADMIN_ID` is set, message yourself on Telegram while the bot is running:

| Command | Description |
|---|---|
| `/status` | All open positions with live P&L |
| `/price` | Live bid/ask for XAUUSD, EURUSD, GBPUSD |
| `/trades` | Last 10 logged trades |
| `/close 100123` | Close a specific position by ticket number |
| `/closeall` | Close all open positions |

The bot also sends you automatic notifications when a position opens or closes.

---

## Trade Dashboard

Open `client/index.html` in a browser to view your trade history.

It reads from `trades.json` and shows:
- All executed trades in a table
- Green rows for BUY, red for SELL
- Filter by symbol
- Dark / light mode toggle
- Refresh button

> The dashboard uses `fetch()` so it needs to be served — not opened as a `file://` URL.
> The easiest way is the **Live Server** extension in VS Code (right-click `index.html` → Open with Live Server).

---

## Project structure

```
├── bot.py              # Main bot — signal listener + trade execution
├── monitor.py          # Remote control + position monitor
├── parser.py           # Signal text parser (standalone version)
├── trades.json         # Trade log (auto-created by bot)
├── session.session     # Telegram session (auto-created on first login)
├── client/
│   └── index.html      # Trade dashboard (pure HTML + React via CDN)
├── get_channels.py     # Helper: list your Telegram channels
├── get_last_messages.py# Helper: read recent messages from a channel
├── test_parser.py      # Test the signal parser
├── test_mt5.py         # Test MT5 connection
└── test_telegram.py    # Test Telegram connection
```

---

## Important notes

**One machine at a time** — never run the bot on two machines using the same `session.session` file simultaneously. Telegram will invalidate the session. If you switch machines, delete the old `session.session` first.

**Demo account first** — test on a demo account before going live. Verify trades are opening correctly with the right SL/TP.

**Lot sizing** — the `LOT` setting in `bot.py` is the total lot per signal. If a signal has 6 TPs, it splits that lot across 6 trades. Make sure your broker's minimum lot allows this.

**Market hours** — MT5 will reject orders when the market is closed. The bot will print the error but won't crash.

---

## Troubleshooting

| Error | Fix |
|---|---|
| `MT5 initialization failed` | Make sure MT5 is open and logged in |
| `Invalid stops` | SL or TP is on the wrong side of the price — usually means market moved a lot since the signal |
| `AuthKeyDuplicatedError` | Delete `session.session` and restart — you ran the bot on two machines at once |
| `Symbol not available` | Add the symbol to MT5 Market Watch |
| Dashboard shows nothing | Make sure `trades.json` exists and serve the file through Live Server |
