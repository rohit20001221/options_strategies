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
date = '05'


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

    print('[x] checking for exit condition')

    historical_data = kite.historical_data(
        nifty_token,
        from_date=datetime.date.today() - datetime.timedelta(weeks=1),
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

            print(f"[x] exited {tradingsymbol}")

        should_enter = True
        entry_trend = None
        positions.clear()


def check_entry_condition():
    global should_enter, entry_trend, positions, nifty_token, instruments, symbol, year, month, date

    if not(should_enter):
        check_exit_conditions()
        return

    print('[x] checking for entry condition')

    historical_data = kite.historical_data(
        nifty_token,
        from_date=datetime.date.today() - datetime.timedelta(weeks=1),
        to_date=datetime.date.today(),
        interval='5minute',
        oi=True,
    )

    df = pd.DataFrame(historical_data)
    df.ta.fisher(append=True)
    df.ta.chop(append=True)
    df['ema'] = ta.ema(df['close'], 100)

    # iloc[-1]
    transform = df['FISHERT_9_1'].iloc[-1]
    signal = df['FISHERTs_9_1'].iloc[-1]
    ema = df['ema'].iloc[-1]
    close = df['close'].iloc[-1]
    is_choppiness_decreasing = ta.sma(ta.decreasing(ta.ema(df['CHOP_14_1_100'])), 5).iloc[-1] == 1
    super_trend_direction = ta.supertrend(low=df['low'], close=df['close'], high=df['high']).iloc[-1]['SUPERTd_7_3.0']

    did_trade = False
    atm = get_atm(kite)

    ce_symbol = get_option_symbol(symbol, year, month, date, atm + 200, 'CE')
    pe_symbol = get_option_symbol(symbol, year, month, date, atm - 200, 'PE')

    if (close > ema and transform > signal) and is_choppiness_decreasing and super_trend_direction == 1:
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

        print(f"[x] entering {pe_symbol} trend: {entry_trend}")
    elif (close < ema and transform < signal) and is_choppiness_decreasing and super_trend_direction == -1:
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

        print(f"[x] entering {ce_symbol} trend: {entry_trend}")

    if did_trade:
        should_enter = False



def start_auto_trade():
    print('[x] starting algo trade ...')
    schedule.every(1).minutes.do(check_entry_condition)

schedule.every(1).day.at('09:20').do(start_auto_trade)

while True:
    schedule.run_pending()
    time.sleep(1)