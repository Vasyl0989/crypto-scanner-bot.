import requests
import time
import datetime as dt
from dataclasses import dataclass
import math

# ====================== НАЛАШТУВАННЯ TELEGRAM ======================
# УВАГА: Вставте сюди свої дані, якщо запускаєте локально. 
# Не публікуйте справжній токен у публічному репозиторії!
TG_BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
TG_CHAT_ID = 'YOUR_TELEGRAM_CHAT_ID'

# ====================== ПАРАМЕТРИ РИЗИКУ ======================
RISK_USDT = 7.8
MAX_POSITION_USDT = 400.0
MIN_RR = 2.5
LEVERAGE = 3
MIN_NOTIONAL_USDT = 5.0

# ====================== ПАРАМЕТРИ ПАТЕРНУ ======================
PARAMS = {
    "60":  dict(lookback=24, tol_touch=0.008, tol_hold=0.015, max_age=20, min_break=0.002), # 1H
    "240": dict(lookback=12, tol_touch=0.012, tol_hold=0.025, max_age=10, min_break=0.003), # 4H
    "D":   dict(lookback=10, tol_touch=0.020, tol_hold=0.030, max_age=7,  min_break=0.005), # 1D
}

# ====================== МОНЕТИ (50 штук) ======================
SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "LINKUSDT", "LTCUSDT", "AVAXUSDT",
    "DOTUSDT", "ADAUSDT", "DOGEUSDT", "BCHUSDT", "ZECUSDT", "TAOUSDT", "ICPUSDT",
    "NEARUSDT", "UNIUSDT", "SUIUSDT", "HYPEUSDT", "ENAUSDT", "TONUSDT", "ETCUSDT",
    "ARBUSDT", "WLDUSDT", "ONDOUSDT", "1000PEPEUSDT", "AAVEUSDT", "TRXUSDT",
    "BNBUSDT", "FILUSDT", "ATOMUSDT", "APTUSDT", "OPUSDT", "INJUSDT", "SEIUSDT",
    "TIAUSDT", "JUPUSDT", "ALGOUSDT", "XLMUSDT", "HBARUSDT", "RUNEUSDT",
    "EGLDUSDT", "SNXUSDT", "CRVUSDT", "DYDXUSDT", "1INCHUSDT", "COMPUSDT",
    "SANDUSDT", "MANAUSDT", "AXSUSDT", "THETAUSDT"
]

BYBIT_URL = "https://api.bybit.com/v5/market"

@dataclass
class Candle:
    t: str
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0

def bybit_get(path: str, **params) -> dict:
    r = requests.get(f"{BYBIT_URL}/{path}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()["result"]

def bybit_candles(symbol: str, interval: str, limit: int = 200) -> list[Candle]:
    rows = bybit_get("kline", category="linear", symbol=symbol, interval=interval, limit=limit)["list"]
    rows.reverse()
    out = []
    for x in rows:
        ts = dt.datetime.utcfromtimestamp(int(x[0]) / 1000).strftime('%Y-%m-%d %H:%M')
        out.append(Candle(ts, float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[5])))
    return out

def send_telegram(text: str):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("Telegram не налаштовано")
        return
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    for i in range(0, len(text), 4000):
        try:
            requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text[i:i+4000], "parse_mode": "HTML"}, timeout=10)
        except Exception as e:
            print(f"Telegram error: {e}")

def atr_pct(candles: list[Candle], period: int = 14) -> float:
    if len(candles) < period + 1: return 0.0
    trs = []
    for i in range(-period, 0):
        c, p = candles[i], candles[i-1]
        trs.append(max(c.h - c.l, abs(c.h - p.c), abs(c.l - p.c)))
    return sum(trs) / period / candles[-1].c * 100

def swing_points(candles: list[Candle], kind: str, wing: int = 3) -> list[float]:
    pts = []
    for i in range(wing, len(candles) - wing):
        w = candles[i-wing:i+wing+1]
        if kind == "high" and candles[i].h == max(x.h for x in w): pts.append(candles[i].h)
        if kind == "low" and candles[i].l == min(x.l for x in w): pts.append(candles[i].l)
    return pts

def volume_ratio(candles: list[Candle], idx: int, period: int = 20) -> float:
    prev = [c.v for c in candles[max(0, idx-period):idx] if c.v > 0]
    if not prev or candles[idx].v <= 0: return 0.0
    return candles[idx].v / (sum(prev) / len(prev))

def find_setups(symbol: str, candles: list[Candle], p: dict, side: str) -> list[dict]:
    out = []
    n = len(candles)
    cur = candles[-1].c
    for b in range(p["lookback"], n - 1):
        if n - 1 - b > p["max_age"]: continue
        window = candles[b - p["lookback"]: b]
        if side == "long":
            level = max(c.h for c in window)
            if not (candles[b].c > level * (1 + p["min_break"]) and candles[b-1].c <= level): continue
            retest = min(c.l for c in candles[b+1:])
            ok = retest <= level * (1 + p["tol_touch"]) and retest >= level * (1 - p["tol_hold"]) and cur > level
        else:
            level = min(c.l for c in window)
            if not (candles[b].c < level * (1 - p["min_break"]) and candles[b-1].c >= level): continue
            retest = max(c.h for c in candles[b+1:])
            ok = retest >= level * (1 - p["tol_touch"]) and retest <= level * (1 + p["tol_hold"]) and cur < level
        if ok:
            out.append(dict(symbol=symbol, side=side, level=level, retest=retest, price=cur, breakout_time=candles[b].t, volume_ratio=volume_ratio(candles, b)))
    return out

def plan_trade(setup: dict, daily: list[Candle], btc_long_ok: bool, btc_short_ok: bool) -> dict | None:
    level, side, price = setup["level"], setup["side"], setup["price"]
    if side == "long" and not btc_long_ok: return None
    if side == "short" and not btc_short_ok: return None

    atr = atr_pct(daily)
    if atr > 5.0: return None

    if side == "long":
        entry = level * 1.003
        stop = min(setup["retest"], level) * 0.985
        highs = sorted(h for h in swing_points(daily[-120:], "high") if h > price * 1.02)
        target = highs[0] * 0.995 if highs else None
    else:
        entry = level * 0.997
        stop = max(setup["retest"], level) * 1.015
        lows = sorted((l for l in swing_points(daily[-120:], "low") if l < price * 0.98), reverse=True)
        target = lows[0] * 1.005 if lows else None
    if target is None: return None

    risk_per_coin = abs(entry - stop)
    reward_per_coin = abs(target - entry)
    rr = reward_per_coin / risk_per_coin if risk_per_coin else 0
    if rr < MIN_RR: return None

    qty = min(RISK_USDT / risk_per_coin, MAX_POSITION_USDT / entry)
    value = qty * entry
    if value < MIN_NOTIONAL_USDT: return None

    return dict(entry=entry, stop=stop, target=target, rr=rr, qty=qty, value=value, profit=qty * reward_per_coin)

def run_scan():
    print(f"[{dt.datetime.now().strftime('%H:%M')}] Починаємо сканування...")
    try:
        btc_daily = bybit_candles("BTCUSDT", "D")
        btc_y = btc_daily[-2]
        btc_ma20 = sum(c.c for c in btc_daily[-20:]) / 20
        btc_cur = btc_daily[-1].c
        btc_long_ok = btc_cur > btc_y.l and btc_cur > btc_ma20
        btc_short_ok = btc_cur < btc_y.h and btc_cur < btc_ma20
    except Exception as e:
        send_telegram(f"Помилка BTC: {e}")
        return

    signals = []
    for sym in SYMBOLS:
        try:
            daily = bybit_candles(sym, "D", limit=120)
            h4 = bybit_candles(sym, "240", limit=100)
            h1 = bybit_candles(sym, "60", limit=100)
        except:
            continue

        for tf_name, candles in [("1H", h1), ("4H", h4), ("1D", daily)]:
            p_key = "60" if tf_name == "1H" else ("240" if tf_name == "4H" else "D")
            p = PARAMS[p_key]
            for side in ("long", "short"):
                for s in find_setups(sym, candles, p, side):
                    plan = plan_trade(s, daily, btc_long_ok, btc_short_ok)
                    if plan:
                        signals.append((tf_name, s, plan))
        time.sleep(0.1)

    if not signals:
        send_telegram(f"🔍 Сканування ({dt.datetime.now().strftime('%H:%M')}). Перевірено {len(SYMBOLS)} монет. Сигналів немає.")
        print("Сигналів немає.")
        return

    signals.sort(key=lambda x: x[2]['rr'], reverse=True)
    
    msg = f"🚀 <b>Знайдено {len(signals)} сигналів</b>\n\n"
    for tf, s, p in signals[:5]:
        icon = "🟢" if s['side'] == 'long' else "🔴"
        msg += (f"{icon} <b>{s['symbol']} {s['side'].upper()} ({tf})</b>\n"
                f"Вхід: {p['entry']:.4f}\nСтоп: {p['stop']:.4f}\nЦіль: {p['target']:.4f}\n"
                f"R:R 1:{p['rr']:.1f} | Об'єм: {p['value']:.0f} USDT\n\n")
    
    send_telegram(msg)
    print(f"Відправлено {len(signals[:5])} сигналів у Telegram.")

def main():
    send_telegram("🤖 Бот-стратег запущений! Сканую 50 монет на 1H, 4H, 1D кожні 4 години.")
    while True:
        run_scan()
        print("Чекаємо 4 години до наступного сканування...")
        time.sleep(4 * 60 * 60)

if __name__ == "__main__":
    main()
