import json

from broker.zerodha import KiteApp

enctoken = "NyK9LPrRyMQ4j071yeNJbBT4ke1DxY/m3iPcvapAvw2nthjD/KqjBAx0n5bFmr+cxn/UyP/TxsNXylprM0uwI7dGR4fgEL//+Zn6GYIZ4Pdxmvy439egPA=="
kite = KiteApp(enctoken=enctoken)

instruments = kite.instruments()
result = dict()

for instrument in instruments:
    result[instrument['tradingsymbol']] = instrument

with open('instruments.json', "w") as f:
    f.write(json.dumps(result, default=str, indent=1))