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

positions = dict()

with open('./instruments.json', 'r') as f:
    instruments = json.loads(f.read())

trend = None

_exit_slope = {
    'UP': lambda ce, pe: pe - ce,
    'DOWN': lambda ce, pe: ce - pe
}

def check_exit_condition():
    try:
        atm = get_atm(kite)
    except:
        return

    ce_symbol = get_option_symbol(symbol, year, month, date, atm, 'CE')
    pe_symbol = get_option_symbol(symbol, year, month, date, atm, 'PE')

    ce_token = instruments[ce_symbol]['instrument_token']
    pe_token = instruments[pe_symbol]['instrument_token']

    try:
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
    except:
        return

    # trend in oi
    ce_trend = ta.sma(ta.increasing(ta.ema(df_ce['oi'])), 5)
    pe_trend = ta.sma(ta.increasing(ta.ema(df_pe['oi'])), 5)

    # calculate the 2nd derative for exiting from the trade
    _slope = ta.slope(ta.slope(_exit_slope[trend](ce_trend, pe_trend))).iloc[-1]
    if _slope < 0:
        for tradingsymbol in positions:
            try:
                kite.place_order(
                    variety=kite.VARIETY_REGULAR,
                    exchange=kite.EXCHANGE_NFO,
                    tradingsymbol=tradingsymbol,
                    transaction_type=kite.TRANSACTION_TYPE_SELL,
                    quantity=instruments[tradingsymbol]['lot_size'], # 1 lot PE
                    product=kite.PRODUCT_NRML,
                    order_type=kite.ORDER_TYPE_MARKET,
                    stoploss=None
                )
            except:
                return

        positions.clear()
    return

def check_entry_condition():
    global trend

    if not(should_enter):
        check_exit_condition()
        return

    try:
        atm = get_atm(kite)
    except:
        return

    ce_symbol = get_option_symbol(symbol, year, month, date, atm, 'CE')
    pe_symbol = get_option_symbol(symbol, year, month, date, atm, 'PE')

    ce_token = instruments[ce_symbol]['instrument_token']
    pe_token = instruments[pe_symbol]['instrument_token']

    try:
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
    except:
        return

    # trend of the oi
    ce_trend = ta.sma(ta.increasing(ta.ema(df_ce['oi'])), 5)
    pe_trend = ta.sma(ta.increasing(ta.ema(df_pe['oi'])), 5)

    # oi crossover
    is_crossover = ta.cross(ce_trend, pe_trend).iloc[-1]

    ce_slope = ta.slope(ce_trend).iloc[-1] # slope for change in oi
    pe_slope = ta.slope(pe_trend).iloc[-1] # slope for change in oi


    did_trade = False

    if is_crossover and ce_slope > pe_slope:
        # BUY THE PUT OPTION DOWN TREND
        try:
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
        except:
            return

        did_trade = True
        trend = 'DOWN'
    elif is_crossover and ce_slope < pe_slope:
        # BUY THE CALL OPTION UP TREND
        try:
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
        except:
            return

        did_trade = True
        trend = 'UP'

    if did_trade:
        should_enter = False

def start_auto_trade():
    schedule.every(1).minutes.do(check_entry_condition)

schedule.every(1).day.at('09:20').do(start_auto_trade)

while True:
    schedule.run_pending()
    time.sleep(1)