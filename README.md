# Forex-model-

# Regime-Conditioned Mean Reversion Engine

An automated quantitative trading algorithm built in Python that interfaces directly with MetaTrader 5 to execute statistical arbitrage on the EUR/USD currency pair. 

This engine is designed to exploit intraday pricing inefficiencies during low-volatility market sessions, utilizing dynamic risk-scaling and macro-regime filters to protect capital from trend-based destruction.

## 🧠 Core Strategy Mechanics

This algorithm relies on a multi-layered filtering system, ensuring it only executes mean-reverting trades when mathematical and macroeconomic conditions align.

* **Statistical Arbitrage (Z-Score):** The core engine calculates the mean over a rolling 20-period window. Trades are triggered only when the price deviates by a strict **1.5 Standard Deviations**, betting on a statistical snap-back to the mean.
* **Dynamic Volatility Scaling (ATR):** Fixed-pip stop losses are retail traps. This algorithm uses a 14-period Average True Range (ATR) to measure live market volatility. The Stop Loss is dynamically placed at **1.5x ATR**, giving the asset exactly enough room to breathe based on current market physics.
* **Macro-Regime Filter (EMA Delta):** Mean-reversion fails during heavy trends. The bot calculates the delta of a 50-period Exponential Moving Average. If the EMA is moving faster than the current ATR, the bot categorizes the market as "Trending" and shuts down, successfully dodging macro-breakouts.
* **Market Micro-Structure (Session Filter):** The algorithm is strictly time-gated to operate between **00:00 and 08:00** (Asian Session), taking advantage of the natural low-liquidity ranging environment before the London and New York volume spikes.

## ⚙️ Engineering & Architecture

* **Broker API Integration:** Seamless tick-data extraction and processing using the official `MetaTrader5` Python library.
* **Vectorized Calculations:** High-performance indicator engineering utilizing `pandas` and `numpy` for rapid rolling-window mathematics.
* **Compounding Risk Management:** Position sizing is mathematically calculated on a per-trade basis. The bot calculates the exact micro-lot size required to risk strictly **1.0%** of total account equity based on the dynamic ATR stop-loss distance.
* **Interactive Telemetry:** Includes an integrated `plotly` charting engine that automatically generates a multi-panel HTML backtest report, plotting the equity curve, Profit/Loss scatter, Z-score oscillator, and precise execution markers over price action.

Markdown
## 🛠️ Installation & Usage

1. **Prerequisites:** You must have [MetaTrader 5](https://www.metatrader5.com/) installed and running on your machine.

2. **Python Dependencies:** Install the required quantitative libraries via terminal:

    ```bash
    pip install MetaTrader5 pandas numpy plotly
    ```

3. **Execution:** Ensure your MT5 terminal has historical M15 data downloaded for your target symbol (default: `EURUSD.pro`). Run the script:

    ```bash
    python main.py
    ```

4. **Diagnostics:** Upon completion, the script outputs a rigorous console autopsy (Win Rate, Drawdown, Average Pip Capture) and opens `algorithmic_backtest_report.html` in your web browser for visual trade inspection.

## ⚠️ Disclaimer
*This repository is for educational and quantitative research purposes only. Algorithmic trading involves significant risk. The author is not responsible for any financial losses incurred from deploying this logic in live market environments.*
