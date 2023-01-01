def get_option_symbol(symbol, year, month, date, strike, type):
    return symbol + year + month + date + strike + type

def get_atm(kite):
    return int((kite.ltp('NSE:NIFTY 50')['NSE:NIFTY 50']['last_price'] // 50) * 50)