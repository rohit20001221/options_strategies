import datetime
import json
import time

import pandas as pd
import pandas_ta as ta
import schedule

from broker.zerodha import KiteApp
from options.utils import get_atm, get_option_symbol

global should_enter, entry_trend, positions, nifty_token, instruments, symbol, year, month, date

with open("auth.json", "r") as f:
    enctoken = json.loads(f.read())["enctoken"]

kite = KiteApp(enctoken=enctoken)

symbol = 'NIFTY'
year = '23'
month = '1'
date = '5'


should_enter = True
entry_trend = None
positions = set()
nifty_token = 256265

with open('./instruments.json', 'r') as f:
    instruments = json.loads(f.read())

_exit_conditions = {
    'UP': lambda transform, signal : transform <= signal,
    'DOWN': lambda transform, signal: transform >= signal
}

def check_exit_conditions():
    global should_enter, entry_trend, positions, nifty_token, instruments, symbol, year, month, date

    historical_data = kite.historical_data(
        nifty_token,
        from_date=datetime.date.today(),
        to_date=datetime.date.today(),
        interval='5minute',
        oi=True,
    )

    df = pd.DataFrame(historical_data)
    df.ta.fisher(append=True)

    transform = df['FISHERT_9_1'].iloc[-1]
    signal = df['FISHERTs_9_1'].iloc[-1]

    if _exit_conditions[entry_trend](transform, signal):
        for tradingsymbol in positions:
            kite.place_order(
                variety=kite.VARIETY_REGULAR,
                exchange=kite.EXCHANGE_NFO,
                tradingsymbol=tradingsymbol,
                transaction_type=kite.TRANSACTION_TYPE_BUY,
                quantity=instruments[tradingsymbol]['lot_size'], # 1 lot PE
                product=kite.PRODUCT_NRML,
                order_type=kite.ORDER_TYPE_MARKET,
                stoploss=None
            )

        should_enter = True
        entry_trend = None


def check_entry_condition():
    global should_enter, entry_trend, positions, nifty_token, instruments, symbol, year, month, date

    if not(should_enter):
        check_exit_conditions()
        return

    historical_data = kite.historical_data(
        nifty_token,
        from_date=datetime.date.today(),
        to_date=datetime.date.today(),
        interval='5minute',
        oi=True,
    )

    df = pd.DataFrame(historical_data)
    df.ta.fisher(append=True)
    df['ema'] = ta.ema(df['close'], 100)

    # iloc[-1]
    transform = df['FISHERT_9_1'].iloc[-1]
    signal = df['FISHERTs_9_1'].iloc[-1]
    ema = df['ema'].iloc[-1]
    close = df['close'].iloc[-1]

    did_trade = False
    atm = get_atm(kite)

    ce_symbol = get_option_symbol(symbol, year, month, date, atm, 'CE')
    pe_symbol = get_option_symbol(symbol, year, month, date, atm, 'PE')

    if close > ema and transform > signal:
        # short sell PE as it is a uptrend
        kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=pe_symbol,
            transaction_type=kite.TRANSACTION_TYPE_SELL,
            quantity=instruments[pe_symbol]['lot_size'], # 1 lot PE
            product=kite.PRODUCT_NRML,
            order_type=kite.ORDER_TYPE_MARKET,
            stoploss=None
        )

        positions.add(pe_symbol)
        did_trade = True
        entry_trend = 'UP'
    elif close < ema and transform < signal:
        # short sell CE as it is a downtrend
        kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=ce_symbol,
            transaction_type=kite.TRANSACTION_TYPE_SELL,
            quantity=instruments[ce_symbol]['lot_size'], # 1 lot CE
            product=kite.PRODUCT_NRML,
            order_type=kite.ORDER_TYPE_MARKET,
            stoploss=None
        )

        positions.add(ce_symbol)
        did_trade = True
        entry_trend = 'DOWN'

    if did_trade:
        should_enter = False



def start_auto_trade():
    schedule.every(1).minutes.do(check_entry_condition)

schedule.every(1).day.at('9:15').do(start_auto_trade)

while True:
    schedule.run_pending()
    time.sleep(1)