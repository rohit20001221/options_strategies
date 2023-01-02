import datetime
import json
import time

import pandas as pd
import pandas_ta as ta
import schedule

from broker.zerodha import KiteApp
from options.utils import get_atm, get_option_symbol

with open("auth.json", "r") as f:
    enctoken = json.loads(f.read())["enctoken"]

kite = KiteApp(enctoken=enctoken)

symbol = 'NIFTY'
year = '23'
month = '1'
date = '05'

should_enter = True

positions = set()

# NIFTY JAN FUT
nifty_fut_token = 8972290

with open('./instruments.json', 'r') as f:
    instruments = json.loads(f.read())

def check_exit_condition():
    return

def check_entry_condition():
    if not(should_enter):
        check_exit_condition()
        return

    atm = get_atm(kite)

    ce_symbol = get_option_symbol(symbol, year, month, date, atm, 'CE')
    pe_symbol = get_option_symbol(symbol, year, month, date, atm, 'PE')

    ce_token = instruments[ce_symbol]['instrument_token']
    pe_token = instruments[pe_symbol]['instrument_token']

    df_ce = pd.DataFrame(kite.historical_data(
        ce_token,
        from_date=datetime.date.today(),
        to_date=datetime.date.today(),
        interval='5minute',
        oi=True,
    ))

    df_pe = pd.DataFrame(kite.historical_data(
        pe_token,
        from_date=datetime.date.today(),
        to_date=datetime.date.today(),
        interval='5minute',
        oi=True,
    ))

    ce_trend = ta.sma(ta.increasing(ta.ema(df_ce['oi'])), 5).iloc[-1]
    pe_trend = ta.sma(ta.increasing(ta.ema(df_pe['oi'])), 5).iloc[-1]
    did_trade = False

    if ce_trend == 1 and pe_trend == 0:
        # BUY THE PUT OPTION
        kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=pe_symbol,
            transaction_type=kite.TRANSACTION_TYPE_BUY,
            quantity=instruments[pe_symbol]['lot_size'], # 1 lot PE
            product=kite.PRODUCT_NRML,
            order_type=kite.ORDER_TYPE_MARKET,
            stoploss=None
        )

        did_trade = True
    elif ce_trend == 0 and pe_trend == 1:
        # BUY THE CALL OPTION
        kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=ce_symbol,
            transaction_type=kite.TRANSACTION_TYPE_BUY,
            quantity=instruments[ce_symbol]['lot_size'], # 1 lot CE
            product=kite.PRODUCT_NRML,
            order_type=kite.ORDER_TYPE_MARKET,
            stoploss=None
        )

        did_trade = True

    if did_trade:
        should_enter = False

def start_auto_trade():
    schedule.every(1).minutes.do(check_entry_condition)

schedule.every(1).day.at('09:20').do(start_auto_trade)

while True:
    schedule.run_pending()
    time.sleep(1)