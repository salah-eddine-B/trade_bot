import MetaTrader5 as mt5

mt5.initialize()

symbol = "XAUUSD"
lot = 0.01

tick = mt5.symbol_info_tick(symbol)

price = tick.ask

request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": symbol,
    "volume": lot,
    "type": mt5.ORDER_TYPE_BUY,
    "price": price,
    "deviation": 20,
    "magic": 123456,
    "comment": "Test Trade",
    "type_time": mt5.ORDER_TIME_GTC,
    "type_filling": mt5.ORDER_FILLING_IOC,
}

result = mt5.order_send(request)

print(result)

mt5.shutdown()