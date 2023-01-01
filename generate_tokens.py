import json

from broker.zerodha import KiteApp

with open("auth.json", "r") as f:
    enctoken = json.loads(f.read())["enctoken"]

kite = KiteApp(enctoken=enctoken)

instruments = kite.instruments()
result = dict()

for instrument in instruments:
    result[instrument['tradingsymbol']] = instrument

with open('instruments.json', "w") as f:
    f.write(json.dumps(result, default=str, indent=1))