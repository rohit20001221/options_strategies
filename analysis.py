import datetime

import pandas as pd
import pandas_ta as ta

from broker.zerodha import KiteApp

enctoken = "uRrxwk+P2BT34jtZw8mi4TXeCY/0iobZEftZ/25eSbp24R/Li0yowiFhJIDvyEvniafNFNQSx3l15kuVzB7CCWjX4MTYram8VivnFnkArA1A8mvOymTmZw=="
kite = KiteApp(enctoken=enctoken)

# NIFTY JAN FUT
nifty_fut_token = 256265

historical_data = kite.historical_data(
    nifty_fut_token,
    from_date=datetime.date.today(),
    to_date=datetime.date.today(),
    interval='5minute',
    oi=True,
)

df = pd.DataFrame(historical_data)
df.ta.fisher(append=True)
df.ta.chop(append=True)

print(df.tail())