#-- IMPORTS
import requests
import time
import datetime
import traceback
import os

# -- By Sean Trewartha, an alert for Bitcoin/Gold crossover with push bullet notification.
#-- CONFIG --
API_KEY = "o.VgP1Xma8pcbRwM9etq9TpYupYTXkxuSq"
RSI_PERIOD = 14
SMA_PERIOD = 14
HISTORY_DAYS = 90
LAST_SIGNAL_FILE = "last_signal.txt"
history = []
last_signal = None

#-- PUSH NOTIFICATION --
def send_push(body):
    headers = {
        "Access-Token": API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "type": "note",
        "title": "Trade Signal",
        "body": body
    }
    try:
        response = requests.post("https://api.pushbullet.com/v2/pushes", json=data, headers=headers)
        print(f"Pushbullet Response: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Failed to send push: {e}")

#-- FILE I/O --
def load_last_signal():
    global last_signal
    if os.path.exists(LAST_SIGNAL_FILE):
        with open(LAST_SIGNAL_FILE, "r") as f:
            last_signal = f.read().strip()

def save_last_signal(signal):
    with open(LAST_SIGNAL_FILE, "w") as f:
        f.write(signal)

#-- PRICE FETCHING --
def fetch_price_history(coin_id, days):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    response = requests.get(url, params=params).json()
    return [point[1] for point in response["prices"]]

def build_daily_ratios():
    print("Fetching BTC history...")
    btc = fetch_price_history("bitcoin", HISTORY_DAYS)
    print("Fetching PAXG history...")
    pax = fetch_price_history("pax-gold", HISTORY_DAYS)
    if len(btc) != len(pax):
        raise Exception(f"BTC and PAXG data mismatch. BTC: {len(btc)}, PAXG: {len(pax)}")
    return [b / p for b, p in zip(btc, pax)]

def get_latest_ratio():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": "bitcoin,pax-gold", "vs_currencies": "usd"}
    response = requests.get(url, params=params).json()
    return response["bitcoin"]["usd"] / response["pax-gold"]["usd"]

#-- TECHNICAL ANALYSIS --
def compute_rsi(data):
    if len(data) < RSI_PERIOD + 1:
        return None
    gains, losses = 0, 0
    for i in range(-RSI_PERIOD, -1):
        diff = data[i + 1] - data[i]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / RSI_PERIOD
    avg_loss = losses / RSI_PERIOD
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def compute_sma(data):
    if len(data) < SMA_PERIOD:
        return None
    return sum(data[-SMA_PERIOD:]) / SMA_PERIOD

#-- STARTUP --
print("Loading price history...")
try:
    history = build_daily_ratios()
    print(f"Loaded {len(history)} days of ratios.")
    load_last_signal()
except Exception as e:
    print(f"Failed to load history: {e}")
    traceback.print_exc()
    history = []

#-- MONITORING LOOP (ONCE PER DAY) --
while True:
    try:
        latest = get_latest_ratio()
        history.append(latest)

        rsi = compute_rsi(history)
        rsi_history = [compute_rsi(history[i - RSI_PERIOD:i + 1]) for i in range(RSI_PERIOD, len(history))]
        sma = compute_sma(rsi_history)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] BTC/PAXG: {latest:.4f}, RSI: {rsi:.2f}, SMA: {sma:.2f}, Last: {last_signal}")

        if rsi is None or sma is None:
            print("Not enough data yet.")
        else:
            if rsi > sma and last_signal != "BUY BTC":
                last_signal = "BUY BTC"
                save_last_signal(last_signal)
                msg = f"BUY BITCOIN\nBTC/PAXG: {latest:.4f}\nRSI: {rsi:.2f}\nSMA: {sma:.2f}"
                send_push(msg)
            elif rsi < sma and last_signal != "BUY GOLD":
                last_signal = "BUY GOLD"
                save_last_signal(last_signal)
                msg = f"BUY GOLD\nBTC/PAXG: {latest:.4f}\nRSI: {rsi:.2f}\nSMA: {sma:.2f}"
                send_push(msg)

    except Exception as e:
        print(f"Error in main loop: {e}")
        traceback.print_exc()

    print("Sleeping 24 hours until next check...\n")
    time.sleep(86400)  #-- sleep for 1 day
