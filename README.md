# 🤖 Crypto Scanner Bot (Bybit)

This bot is an autonomous trading system that scans the futures market on the **Bybit** exchange and looks for the **"Breakout + Retest"** pattern on three timeframes (1H, 4H, 1D).

## 🚀 Features
*   **Scans 50 coins** simultaneously.
*   **Filters out false signals**: checks volume, volatility (ATR), and Bitcoin trend (MA20).
*   **Risk Management**: automatically calculates Stop-Loss and Take-Profit so that the risk per trade is no more than **7.8 USDT**. Risk-to-Reward ratio (R:R) is at least **1:2.5**.
*   **Telegram Integration**: sends the best signals directly to your chat.

## 🛠️ Technologies
*   Python 3
*   Bybit API (v5)
*   Telegram Bot API

## ⚙️ How to Setup
1. Install dependencies: `pip install requests`.
2. Open `strategy.py` and insert your token and Chat ID into the `TG_BOT_TOKEN` and `TG_CHAT_ID` variables.
3. Run the bot: `python3 strategy.py`.

## ⚠️ Disclaimer
This bot is a market analysis tool, not financial advice. Always verify signals manually and use stop-losses.
