import json
import time

import pandas as pd
import pandas_ta as ta
import redis
import schedule

from broker.zerodha import KiteApp
from options.utils import get_atm_price_from_redis, get_option_symbol

redis_client = redis.Redis()

with open("auth.json", "r") as f:
    enctoken = json.loads(f.read())["enctoken"]

kite = KiteApp(enctoken=enctoken)

symbol = 'NIFTY'
year = '23'
month = '1'
date = '19'

should_enter = True

positions = dict()

with open('./instruments.json', 'r') as f:
    instruments = json.loads(f.read())

def check_exit_condition():
    global should_enter

    for position in positions:
        if position['is_active']:
            instrument_token = position['instrument_token']
            entry_price = position['entry_price']

            live_data = redis_client.json().get(f"live:{instrument_token}")
            profit_price = entry_price  + 5
            loss_price = entry_price - 2

            if live_data['last_price'] >= profit_price or live_data['last_price'] <= loss_price:
                kite.place_order(
                    variety=kite.VARIETY_REGULAR,
                    exchange=kite.EXCHANGE_NFO,
                    tradingsymbol=position['tradingsymbol'],
                    transaction_type=kite.TRANSACTION_TYPE_SELL,
                    quantity=instruments[position['tradingsymbol']]['lot_size'], # 1 lot PE
                    product=kite.PRODUCT_NRML,
                    order_type=kite.ORDER_TYPE_LIMIT,
                    price=live_data['depth']['buy'][1]['price'],
                    stoploss=None
                )

                positions[position['tradingsymbol']]['is_open'] = False
                should_enter = True

    return

def check_entry_condition():
    if not(should_enter):
        return

    atm = get_atm_price_from_redis(redis_client)

    ce = get_option_symbol(
        symbol, year, month, date, atm, 'CE'
    )
    pe = get_option_symbol(
        symbol, year, month, date, atm, 'PE'
    )

    ce_instrument = instruments[ce]['instrument_token']
    pe_instrument = instruments[pe]['instrument_token']

    prev_oi_ce = redis_client.json().get(f"oi:{ce_instrument}")['oi']
    prev_oi_pe = redis_client.json().get(f"oi:{pe_instrument}")['oi']

    # consider change in OI
    historical_data_ce = pd.DataFrame(
        redis_client.json().get(f'historical:{ce_instrument}')['data']
    )
    historical_data_ce.index = pd.to_datetime(
        historical_data_ce['timestamp']
    )

    historical_data_pe = pd.DataFrame(
        redis_client.json().get(
            f'historical:{pe_instrument}'
        )['data']
    )
    historical_data_pe.index = pd.to_datetime(
        historical_data_pe['timestamp']
    )

    df_oi_ce = historical_data_ce['oi'].resample('5T').last() - prev_oi_ce
    df_oi_pe = historical_data_pe['oi'].resample('5T').last() - prev_oi_pe

    ce_oi_increasing = ta.increasing(ta.sma(df_oi_ce)).iloc[-1]
    pe_oi_increasing = ta.increasing(ta.sma(df_oi_pe)).iloc[-1]

    live_ce = redis_client.json().get(
        f"live:{ce_instrument}"
    )

    live_pe = redis_client.json().get(
        f"live:{pe_instrument}"
    )

    # ce increasing pe increasing
    if ce_oi_increasing == 1 and pe_oi_increasing == 0:
        # down trend
        kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=pe,
            transaction_type=kite.TRANSACTION_TYPE_BUY,
            quantity=instruments[pe]['lot_size'], # 1 lot PE
            product=kite.PRODUCT_NRML,
            order_type=kite.ORDER_TYPE_LIMIT,
            price=live_pe['depth']['sell'][1]['price'],
            stoploss=None
        )

        if pe not in positions:
            positions[pe] = {
                'tradingsymbol': pe,
                'entry_price': live_pe['depth']['sell'][1]['price'],
                'instrument_token': pe_instrument,
                'is_open': True
            }
        else:
            positions[pe]['is_open'] = True
            positions[pe]['entry_price'] += live_pe['depth']['sell'][1]['price']
            positions[pe]['entry_price'] /= 2

        should_enter = False
        return
    elif ce_oi_increasing == 0 and pe_oi_increasing == 1:
        # up trend
        kite.place_order(
            variety=kite.VARIETY_REGULAR,
            exchange=kite.EXCHANGE_NFO,
            tradingsymbol=ce,
            transaction_type=kite.TRANSACTION_TYPE_BUY,
            quantity=instruments[ce]['lot_size'], # 1 lot CE
            product=kite.PRODUCT_NRML,
            order_type=kite.ORDER_TYPE_LIMIT,
            price=live_pe['depth']['sell'][1]['price'],
            stoploss=None
        )

        if ce not in positions:
            positions[ce] = {
                'tradingsymbol': ce,
                'entry_price': live_ce['depth']['sell'][1]['price'],
                'instrument_token': ce_instrument,
                'is_open': True
            }
        else:
            positions[ce]['is_open'] = True
            positions[ce]['entry_price'] += live_ce['depth']['sell'][1]['price']
            positions[ce]['entry_price'] /= 2

        should_enter = False
        return

def start_auto_trade():
    print('[x] auto trade started')
    schedule.every(10).seconds.do(check_entry_condition)

schedule.every(1).day.at('09:20').do(start_auto_trade)

while True:
    schedule.run_pending()
    time.sleep(1)