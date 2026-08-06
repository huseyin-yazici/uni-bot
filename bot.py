import json
import os
import urllib.request
from datetime import datetime, timezone

STATE_FILE = "state.json"
START_CASH = 1000.0
HISTORY_MAX = 200
TRADES_MAX = 30
PIVOT_WINDOW = 3
COOLDOWN_TICKS = 3
SUPPORT_MARGIN = 0.006   # buy if price within 0.6% above last support
RESISTANCE_MARGIN = 0.006  # sell if price within 0.6% below last resistance
BUY_FRACTION = 0.35   # fraction of cash spent per buy
SELL_FRACTION = 0.6   # fraction of coins sold per sell


def fetch_price():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=uniswap&vs_currencies=usd"
    req = urllib.request.Request(url, headers={"User-Agent": "uni-bot/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    return float(data["uniswap"]["usd"])


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {
        "history": [],
        "cash": START_CASH,
        "coins": 0.0,
        "trades": [],
        "tick": 0,
        "last_action_tick": -100,
    }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def find_pivots(history, window=PIVOT_WINDOW):
    supports, resistances = [], []
    n = len(history)
    for i in range(window, n - window):
        center = history[i]["price"]
        seg = history[i - window: i + window + 1]
        if all(d["price"] >= center for d in seg):
            supports.append(history[i])
        if all(d["price"] <= center for d in seg):
            resistances.append(history[i])
    return supports, resistances


def main():
    state = load_state()
    price = fetch_price()
    now = datetime.now(timezone.utc).isoformat()

    state["tick"] += 1
    state["history"].append({"t": now, "price": price, "tick": state["tick"]})
    state["history"] = state["history"][-HISTORY_MAX:]

    supports, resistances = find_pivots(state["history"])
    support_level = supports[-1]["price"] if supports else None
    resistance_level = resistances[-1]["price"] if resistances else None

    cooldown_ok = state["tick"] - state["last_action_tick"] > COOLDOWN_TICKS
    action = None

    if cooldown_ok and support_level and price <= support_level * (1 + SUPPORT_MARGIN) and state["cash"] > 5:
        spend = state["cash"] * BUY_FRACTION
        bought = spend / price
        state["cash"] = round(state["cash"] - spend, 2)
        state["coins"] = round(state["coins"] + bought, 6)
        state["trades"].insert(0, {"type": "AL", "price": price, "amount": bought, "time": now})
        state["last_action_tick"] = state["tick"]
        action = "AL"
    elif cooldown_ok and resistance_level and price >= resistance_level * (1 - RESISTANCE_MARGIN) and state["coins"] > 0.0001:
        sell_amt = state["coins"] * SELL_FRACTION
        gain = sell_amt * price
        state["coins"] = round(state["coins"] - sell_amt, 6)
        state["cash"] = round(state["cash"] + gain, 2)
        state["trades"].insert(0, {"type": "SAT", "price": price, "amount": sell_amt, "time": now})
        state["last_action_tick"] = state["tick"]
        action = "SAT"

    state["trades"] = state["trades"][:TRADES_MAX]
    state["support_level"] = support_level
    state["resistance_level"] = resistance_level
    state["last_price"] = price
    state["last_updated"] = now
    state["portfolio_value"] = round(state["cash"] + state["coins"] * price, 2)

    save_state(state)
    print(f"[{now}] price={price} action={action} portfolio={state['portfolio_value']}")


if __name__ == "__main__":
    main()