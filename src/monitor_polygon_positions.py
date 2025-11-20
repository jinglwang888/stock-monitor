import pandas as pd
import os
import datetime
import requests

HOLDINGS_FILE = 'data/my_current_holdings.csv'
POLYGON_API_KEY = os.environ.get('POLYGON_API_KEY', 'YOUR_POLYGON_API_KEY_HERE')
BASE_URL = "https://api.polygon.io"

A_PERCENT=10.0; B_PERCENT=60.0; C_PERCENT=20.0; D_PERCENT=10.0
A=A_PERCENT/100; B=B_PERCENT/100; C=C_PERCENT/100; D=D_PERCENT/100
MIN_HOLD_DAYS=30

def fetch_daily_prices_for_ticker(ticker,start_date,end_date):
    url=f"{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
    params={"adjusted":"true","sort":"asc","limit":5000,"apiKey":POLYGON_API_KEY}
    try:
        r=requests.get(url,params=params,timeout=20); r.raise_for_status()
        data=r.json().get("results",[])
        if not data: return None
        df=pd.DataFrame(data)
        df["t"]=pd.to_datetime(df["t"],unit="ms").dt.date
        df=df.rename(columns={"c":"Close","o":"Open","h":"High","l":"Low","v":"Volume"}).set_index("t")
        return df[["Open","High","Low","Close","Volume"]]
    except Exception:
        return None

def get_most_recent_data(df):
    if df is not None and not df.empty:
        return df.iloc[-1]
    return None

def monitor_positions():
    try:
        hd=pd.read_csv(HOLDINGS_FILE)
        hd["Purchase Date"]=pd.to_datetime(hd["Purchase Date"]).dt.date
    except Exception:
        return []

    today=datetime.date.today()
    alerts=[]

    for _,row in hd.iterrows():
        ticker=row["Ticker"]
        pd0=row["Purchase Date"]
        price=row["Purchase Price"]

        df=fetch_daily_prices_for_ticker(ticker,pd0,today)
        last=get_most_recent_data(df)
        if last is None:
            continue

        current_date=last.name
        close=float(last["Close"])
        high=float(last["High"])
        low=float(last["Low"])
        exit_price=(high+low)/2
        days=(current_date-pd0).days

        sell=False
        reason=""

        if days>=MIN_HOLD_DAYS:
            if close < price*(1-A):
                sell=True; reason="Stop loss"
            elif close > price*(1+B):
                sell=True; reason="Profit target"
            elif close > price*(1+C):
                high_since=df.loc[df.index>=pd0]["Close"].max()
                trail=high_since*(1-D)
                if close<trail:
                    sell=True; reason="Trailing stop"

        if sell:
            ret=(exit_price-price)/price*100
            alerts.append({"Ticker":ticker,"Reason":reason,"Return %":round(ret,2),"Days":days})

    return alerts

if __name__=="__main__":
    print(monitor_positions())
