import pandas as pd
import os
import datetime
import requests

# ====== CONFIGURATION ======
# --- Files ---
HOLDINGS_FILE = 'data/my_current_holdings.csv'

# --- API ---
POLYGON_API_KEY = os.environ.get('POLYGON_API_KEY', 'j8tt2QIhU0pfMFIaT4j0pjD8nUJpp3y7')  # Replace for local testing
BASE_URL = "https://api.polygon.io"

# --- Exit Strategy Parameters (Match your simulation parameters) ---
A_PERCENT = 10.0  # Sell if down by more than A% after one month
B_PERCENT = 60.0  # Sell if up by more than B% after one month
C_PERCENT = 20.0  # Trailing stop loss activated at C% gain
D_PERCENT = 10.0  # Trailing stop loss percentage

# Convert percentages to decimal for calculations
A = A_PERCENT / 100.0
B = B_PERCENT / 100.0
C = C_PERCENT / 100.0
D = D_PERCENT / 100.0

# Minimum holding period in days
MIN_HOLD_DAYS = 30


def fetch_daily_prices_for_ticker(ticker, start_date, end_date):
    print(f"  Fetching data for {ticker} from {start_date} to {end_date}...")
    url = f"{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": 5000,
        "apiKey": POLYGON_API_KEY,
    }
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json().get("results", [])
        if not data:
            print(f"    No data found for {ticker} from {start_date} to {end_date}")
            return None

        df = pd.DataFrame(data)
        df["t"] = pd.to_datetime(df["t"], unit="ms").dt.date
        df.set_index("t", inplace=True)
        df.rename(
            columns={"c": "Close", "v": "Volume", "h": "High", "l": "Low", "o": "Open"},
            inplace=True,
        )
        return df[["Open", "High", "Low", "Close", "Volume"]]
    except requests.exceptions.RequestException as e:
        print(f"    Request failed for {ticker}: {e}")
        return None


def get_most_recent_data(ticker_data_df):
    if ticker_data_df is not None and not ticker_data_df.empty:
        return ticker_data_df.iloc[-1]
    return None


def monitor_positions():
    print(
        f"\n--- Stock Monitoring Started: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---"
    )
    print(f"Using holdings file: {os.path.abspath(HOLDINGS_FILE)}")
    alerts = []

    # Load holdings
    try:
        holdings_df = pd.read_csv(HOLDINGS_FILE)
        required_cols = ["Ticker", "Purchase Date", "Purchase Price", "Shares"]
        if not all(col in holdings_df.columns for col in required_cols):
            print(
                f"Error: Holdings file must contain columns: {required_cols}. "
                f"Found: {list(holdings_df.columns)}"
            )
            return alerts
        holdings_df["Purchase Date"] = pd.to_datetime(
            holdings_df["Purchase Date"]
        ).dt.date
        print(f"Loaded {len(holdings_df)} positions from {HOLDINGS_FILE}.")
    except FileNotFoundError:
        print(f"Error: Holdings file '{HOLDINGS_FILE}' not found.")
        return alerts
    except Exception as e:
        print(f"Error loading holdings: {e}")
        return alerts

    today = datetime.date.today()

    # Process each position
    for _, row in holdings_df.iterrows():
        ticker = row["Ticker"]
        purchase_date = row["Purchase Date"]
        purchase_price = row["Purchase Price"]
        shares = row["Shares"]

        print(f"\nAnalyzing {ticker}:")
        print(f"  Purchase Date: {purchase_date}, Price: {purchase_price}, Shares: {shares}")

        fetch_start_date = purchase_date
        fetch_end_date = today + datetime.timedelta(days=5)

        ticker_historical_data = fetch_daily_prices_for_ticker(
            ticker, fetch_start_date, fetch_end_date
        )
        recent_data = get_most_recent_data(ticker_historical_data)

        if recent_data is None:
            print(f"  Skipping {ticker}: Could not get recent price data.")
            continue

        current_date = recent_data.name
        current_close = recent_data["Close"]
        current_high = recent_data["High"]
        current_low = recent_data["Low"]

        current_exit_price = (current_high + current_low) / 2.0
        days_held = (current_date - purchase_date).days

        sell_triggered = False
        trigger_reason = ""

        if days_held < MIN_HOLD_DAYS:
            print(
                f"  Held {days_held} days (< {MIN_HOLD_DAYS}). Skipping sell rules for now."
            )
            continue

        # Rule A: stop loss
        if current_close < purchase_price * (1 - A):
            sell_triggered = True
            trigger_reason = (
                f"Down > {A_PERCENT}% "
                f"({(((current_close - purchase_price) / purchase_price) * 100):.2f}%) "
                f"from purchase price {purchase_price:.2f}"
            )
        # Rule B: profit taking
        elif current_close > purchase_price * (1 + B):
            sell_triggered = True
            trigger_reason = (
                f"Up > {B_PERCENT}% "
                f"({(((current_close - purchase_price) / purchase_price) * 100):.2f}%) "
                f"from purchase price {purchase_price:.2f}"
            )
        # Rule C/D: trailing stop
        elif current_close > purchase_price * (1 + C):
            if ticker_historical_data is not None and not ticker_historical_data.empty:
                relevant_history = ticker_historical_data.loc[
                    ticker_historical_data.index >= purchase_date
                ]
                highest_close_since_purchase = relevant_history["Close"].max()
                trailing_stop_price = highest_close_since_purchase * (1 - D)
                if current_close < trailing_stop_price:
                    sell_triggered = True
                    trigger_reason = (
                        f"Trailing stop triggered (current: {current_close:.2f}, "
                        f"stop: {trailing_stop_price:.2f}) "
                        f"based on high {highest_close_since_purchase:.2f}"
                    )

        return_percent = ((current_exit_price - purchase_price) / purchase_price) * 100

        if sell_triggered:
            print(f"  >>> SELL TRIGGERED: {trigger_reason}")
            alerts.append(
                {
                    "Ticker": ticker,
                    "Reason": trigger_reason,
                    "Purchase Date": purchase_date.strftime("%Y-%m-%d"),
                    "Purchase Price": f"{purchase_price:.2f}",
                    "Current Date": current_date.strftime("%Y-%m-%d"),
                    "Current Price (Close)": f"{current_close:.2f}",
                    "Recommended Exit Price": f"{current_exit_price:.2f}",
                    "Return (%)": f"{return_percent:.2f}",
                    "Days Held": days_held,
                }
            )
        else:
            print(
                f"  No sell trigger. Current Return: {return_percent:.2f}% "
                f"({days_held} days held)."
            )

    return alerts


if __name__ == "__main__":
    sell_alerts = monitor_positions()
    print("\n===== FINAL RESULT =====")
    if sell_alerts:
        print("!!! SELL ALERTS !!!")
        for alert in sell_alerts:
            print(f"\nTicker: {alert['Ticker']}")
            print(f"  Reason: {alert['Reason']}")
            print(
                f"  Purchase: {alert['Purchase Date']} @ ${alert['Purchase Price']}"
            )
            print(
                f"  Current: {alert['Current Date']} @ ${alert['Current Price (Close)']}"
            )
            print(
                f"  Recommended Exit Price: ${alert['Recommended Exit Price']}"
            )
            print(f"  Return: {alert['Return (%)']}% (Days Held: {alert['Days Held']})")
    else:
        print("No sell alerts triggered today.")
