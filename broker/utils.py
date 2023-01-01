import datetime
import struct
from urllib.parse import quote_plus as encode_url

EXCHANGE_MAP = {
    "nse": 1,
    "nfo": 2,
    "cds": 3,
    "bse": 4,
    "bfo": 5,
    "bcd": 6,
    "mcx": 7,
    "mcxsx": 8,
    "indices": 9,
    "bsecds": 6,
}

# Available streaming modes.
MODE_FULL = "full"
MODE_QUOTE = "quote"
MODE_LTP = "ltp"

def _parse_binary(bin):
    """Parse binary data to a (list of) ticks structure."""
    packets = _split_packets(bin)  # split data to individual ticks packet
    data = []

    for packet in packets:
        instrument_token = _unpack_int(packet, 0, 4)
        segment = instrument_token & 0xff  # Retrive segment constant from instrument_token

        # Add price divisor based on segment
        if segment == EXCHANGE_MAP["cds"]:
            divisor = 10000000.0
        elif segment == EXCHANGE_MAP["bcd"]:
            divisor = 10000.0
        else:
            divisor = 100.0

        # All indices are not tradable
        tradable = False if segment == EXCHANGE_MAP["indices"] else True

        # LTP packets
        if len(packet) == 8:
            data.append({
                "tradable": tradable,
                "mode": MODE_LTP,
                "instrument_token": instrument_token,
                "last_price": _unpack_int(packet, 4, 8) / divisor
            })
        # Indices quote and full mode
        elif len(packet) == 28 or len(packet) == 32:
            mode = MODE_QUOTE if len(packet) == 28 else MODE_FULL

            d = {
                "tradable": tradable,
                "mode": mode,
                "instrument_token": instrument_token,
                "last_price": _unpack_int(packet, 4, 8) / divisor,
                "ohlc": {
                    "high": _unpack_int(packet, 8, 12) / divisor,
                    "low": _unpack_int(packet, 12, 16) / divisor,
                    "open": _unpack_int(packet, 16, 20) / divisor,
                    "close": _unpack_int(packet, 20, 24) / divisor
                }
            }

            # Compute the change price using close price and last price
            d["change"] = 0
            if (d["ohlc"]["close"] != 0):
                d["change"] = (d["last_price"] - d["ohlc"]["close"]) * 100 / d["ohlc"]["close"]

            # Full mode with timestamp
            if len(packet) == 32:
                try:
                    timestamp = datetime.fromtimestamp(_unpack_int(packet, 28, 32))
                except Exception:
                    timestamp = None

                d["exchange_timestamp"] = timestamp

            data.append(d)
        # Quote and full mode
        elif len(packet) == 44 or len(packet) == 184:
            mode = MODE_QUOTE if len(packet) == 44 else MODE_FULL

            d = {
                "tradable": tradable,
                "mode": mode,
                "instrument_token": instrument_token,
                "last_price": _unpack_int(packet, 4, 8) / divisor,
                "last_traded_quantity": _unpack_int(packet, 8, 12),
                "average_traded_price": _unpack_int(packet, 12, 16) / divisor,
                "volume_traded": _unpack_int(packet, 16, 20),
                "total_buy_quantity": _unpack_int(packet, 20, 24),
                "total_sell_quantity": _unpack_int(packet, 24, 28),
                "ohlc": {
                    "open": _unpack_int(packet, 28, 32) / divisor,
                    "high": _unpack_int(packet, 32, 36) / divisor,
                    "low": _unpack_int(packet, 36, 40) / divisor,
                    "close": _unpack_int(packet, 40, 44) / divisor
                }
            }

            # Compute the change price using close price and last price
            d["change"] = 0
            if (d["ohlc"]["close"] != 0):
                d["change"] = (d["last_price"] - d["ohlc"]["close"]) * 100 / d["ohlc"]["close"]

            # Parse full mode
            if len(packet) == 184:
                try:
                    last_trade_time = datetime.fromtimestamp(_unpack_int(packet, 44, 48))
                except Exception:
                    last_trade_time = None

                try:
                    timestamp = datetime.fromtimestamp(_unpack_int(packet, 60, 64))
                except Exception:
                    timestamp = None

                d["last_trade_time"] = last_trade_time
                d["oi"] = _unpack_int(packet, 48, 52)
                d["oi_day_high"] = _unpack_int(packet, 52, 56)
                d["oi_day_low"] = _unpack_int(packet, 56, 60)
                d["exchange_timestamp"] = timestamp

                # Market depth entries.
                depth = {
                    "buy": [],
                    "sell": []
                }

                # Compile the market depth lists.
                for i, p in enumerate(range(64, len(packet), 12)):
                    depth["sell" if i >= 5 else "buy"].append({
                        "quantity": _unpack_int(packet, p, p + 4),
                        "price": _unpack_int(packet, p + 4, p + 8) / divisor,
                        "orders": _unpack_int(packet, p + 8, p + 10, byte_format="H")
                    })

                d["depth"] = depth

            data.append(d)

    return data

def _unpack_int(bin, start, end, byte_format="I"):
    """Unpack binary data as unsgined interger."""
    return struct.unpack(">" + byte_format, bin[start:end])[0]

def _split_packets(bin):
    """Split the data to individual packets of ticks."""
    # Ignore heartbeat data.
    if len(bin) < 2:
        return []

    number_of_packets = _unpack_int(bin, 0, 2, byte_format="H")
    packets = []

    j = 2
    for i in range(number_of_packets):
        packet_length = _unpack_int(bin, j, j + 2, byte_format="H")
        packets.append(bin[j + 2: j + 2 + packet_length])
        j = j + 2 + packet_length

    return packets

def get_websocket_url(enctoken="", userid=""):
    enc_token = encode_url(enctoken)

    uri = f"wss://ws.zerodha.com/?api_key=kitefront&user_id={userid}&enctoken={enc_token}&uid=1670136686203&user-agent=kite3-web&version=3.0.7"
    return uri