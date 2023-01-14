NIFTY_50 = 256265

def get_option_symbol(symbol, year, month, date, strike, type):
    return f"{symbol}{year}{month}{date}{strike}{type}"

def get_atm(kite):
    return int((kite.ltp('NSE:NIFTY 50')['NSE:NIFTY 50']['last_price'] // 50) * 50)

def get_atm_price_from_redis(redis_client):
    live_price = redis_client.json().get(f'live:{NIFTY_50}')['last_price']

    strike = (live_price // 50) * 50

    d1 = (abs(live_price - strike), strike)
    d2 = (abs(live_price - strike + 50), strike - 50)
    d3 = (abs(live_price - strike - 50), strike + 50)

    d = min(d1, d2, d3)
    return int(d[1])