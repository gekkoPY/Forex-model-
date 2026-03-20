import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==========================================
# QUANTITATIVE TRADING ENGINE
# Strategy: Regime-Conditioned Mean Reversion
# Asset: EUR/USD (15-Minute Timeframe)
# ==========================================

# --- 1. CONFIGURATION & RISK MANAGEMENT ---
SYMBOL = "EURUSD.pro"
TIMEFRAME = mt5.TIMEFRAME_M15

# Testing Period: High Interest Rate Macro Regime
START_DATE = datetime(2023, 1, 1)
END_DATE = datetime(2024, 12, 31)

# Compounding Risk Parameters
STARTING_BALANCE = 25000.0
RISK_PERCENT = 0.01          # Risk exactly 1% of current equity per trade
LEVERAGE = 20                # ESMA Retail Limit
# ------------------------------------------

print(f"Connecting to MT5 and fetching {SYMBOL} data...")
if not mt5.initialize():
    print("MT5 initialization failed. Ensure terminal is open.")
    quit()

# Fetch tick data from broker
rates = mt5.copy_rates_range(SYMBOL, TIMEFRAME, START_DATE, END_DATE)
mt5.shutdown()

if rates is None or len(rates) == 0:
    print(f"Failed to fetch data. Check symbol name and MT5 history.")
    quit()

# Structure data into a Pandas DataFrame
df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df.set_index('time', inplace=True)
df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'}, inplace=True)

# --- 2. STATISTICAL PARAMETERS ---
MEAN_WINDOW = 20        # 5-hour micro-window for mean calculation
Z_ENTRY = 1.5           # Aggressive standard deviation threshold
EMA_PERIOD = 50         # Trend filter baseline
ATR_PERIOD = 14         # Volatility measurement for dynamic stops
SL_MULTIPLIER = 1.5     # Dynamic Stop Loss distance based on ATR
# ---------------------------------

# --- 3. INDICATOR ENGINEERING ---
# Z-Score (Mean Reversion Trigger)
df['Mean'] = df['Close'].rolling(window=MEAN_WINDOW).mean()
df['StdDev'] = df['Close'].rolling(window=MEAN_WINDOW).std()
df['ZScore'] = (df['Close'] - df['Mean']) / df['StdDev']

# Average True Range (Volatility Profiling)
df['Prev_Close'] = df['Close'].shift(1)
df['TR'] = df[['High', 'Prev_Close']].max(axis=1) - df[['Low', 'Prev_Close']].min(axis=1)
df['ATR'] = df['TR'].rolling(window=ATR_PERIOD).mean()

# Bhatti Momentum Filter (Ensuring market is ranging, not trending)
df['EMA_Now'] = df['Close'].ewm(span=EMA_PERIOD, adjust=False).mean()
df['EMA_Prev'] = df['EMA_Now'].shift(5)
df['Momentum_OK'] = np.abs(df['EMA_Now'] - df['EMA_Prev']) < df['ATR']

# Clean NaN values from rolling windows
df.dropna(inplace=True)

# --- 4. BACKTEST EXECUTION ENGINE ---
account_balance = STARTING_BALANCE
equity_curve = []
trades_log = []

trade_active = False
entry_price = 0.0
stop_loss = 0.0
position_size_usd = 0.0
direction = 0
entry_time = None
last_recorded_day = df.index[0].date()

for i in range(len(df)):
    current_time = df.index[i]
    close = df['Close'].iloc[i]
    high = df['High'].iloc[i]
    low = df['Low'].iloc[i]
    mean = df['Mean'].iloc[i]
    zscore = df['ZScore'].iloc[i]
    atr = df['ATR'].iloc[i]
    mom_ok = df['Momentum_OK'].iloc[i]
    
    # --- POSITION MANAGEMENT ---
    if trade_active:
        exit_price = 0.0
        trade_closed = False
        
        # Long Exit Logic
        if direction == 1:
            if low <= stop_loss:      # Stop Loss Hit
                exit_price = stop_loss
                trade_closed = True
            elif close >= mean:       # Take Profit (Mean Reversion Reached)
                exit_price = close
                trade_closed = True
                
        # Short Exit Logic
        elif direction == -1:
            if high >= stop_loss:     # Stop Loss Hit
                exit_price = stop_loss
                trade_closed = True
            elif close <= mean:       # Take Profit (Mean Reversion Reached)
                exit_price = close
                trade_closed = True
                
        # Settlement & PnL Calculation
        if trade_closed:
            price_diff_real = (exit_price - entry_price) if direction == 1 else (entry_price - exit_price)
            trade_pnl = position_size_usd * (price_diff_real / entry_price)
            account_balance += trade_pnl
            trade_active = False
            
            abs_price_diff = abs(exit_price - entry_price)
            pct_move = (abs_price_diff / entry_price) * 100
            pip_move = abs_price_diff * 10000 
            
            trades_log.append({
                'Entry_Time': entry_time,
                'Exit_Time': current_time,
                'Entry_Price': entry_price,
                'Direction': direction,
                'Duration': current_time - entry_time,
                'PnL': trade_pnl,
                'Win': 1 if trade_pnl > 0 else 0,
                'Pct_Move': pct_move,
                'Pip_Move': pip_move
            })
            
    # --- SIGNAL GENERATION ---
    # Time Filter: Only execute during Asian Session (00:00 - 08:00) when volatility is constrained
    if not trade_active and (0 <= current_time.hour < 8) and mom_ok:
        
        # Bullish Mean Reversion Signal
        if zscore <= -Z_ENTRY:
            direction = 1
            entry_price = close
            stop_loss = entry_price - (atr * SL_MULTIPLIER)
            signal_triggered = True
            
        # Bearish Mean Reversion Signal
        elif zscore >= Z_ENTRY:
            direction = -1
            entry_price = close
            stop_loss = entry_price + (atr * SL_MULTIPLIER)
            signal_triggered = True
            
        else:
            signal_triggered = False
            
        # Risk & Sizing Calculation
        if signal_triggered:
            risk_amount = account_balance * RISK_PERCENT
            sl_distance_pct = abs(entry_price - stop_loss) / entry_price
            theoretical_size = risk_amount / sl_distance_pct
            max_allowed_size = account_balance * LEVERAGE
            position_size_usd = min(theoretical_size, max_allowed_size)
            
            trade_active = True
            entry_time = current_time

    # Record daily equity for charting
    if current_time.date() != last_recorded_day:
        equity_curve.append({'Date': last_recorded_day, 'Equity': account_balance})
        last_recorded_day = current_time.date()

equity_curve.append({'Date': last_recorded_day, 'Equity': account_balance})

# --- 5. STRATEGY AUTOPSY & METRICS ---
total_trades = len(trades_log)
if total_trades > 0:
    win_rate = (sum([t['Win'] for t in trades_log]) / total_trades) * 100
    total_seconds = sum([t['Duration'].total_seconds() for t in trades_log])
    avg_seconds = total_seconds / total_trades
    avg_duration_str = f"{int(avg_seconds // 3600)}h {int((avg_seconds % 3600) // 60)}m"
    avg_pct_move = sum([t['Pct_Move'] for t in trades_log]) / total_trades
    avg_pip_move = sum([t['Pip_Move'] for t in trades_log]) / total_trades
else:
    win_rate = 0.0
    avg_duration_str = "0h 0m"
    avg_pct_move = 0.0
    avg_pip_move = 0.0

results_df = pd.DataFrame(equity_curve).set_index('Date')
total_return = ((account_balance - STARTING_BALANCE) / STARTING_BALANCE) * 100

results_df['Peak'] = results_df['Equity'].cummax()
results_df['Drawdown'] = (results_df['Equity'] - results_df['Peak']) / results_df['Peak'] * 100
max_drawdown = results_df['Drawdown'].min()

print(f"\n=== STRATEGY AUTOPSY (Z=1.5 | 2023-2024) ===")
print(f"Total Trades Taken  : {total_trades}")
print(f"Win Rate            : {win_rate:.2f}%")
print(f"Avg Time in Trade   : {avg_duration_str}")
print(f"Avg Move Per Trade  : {avg_pip_move:.1f} pips ({avg_pct_move:.3f}%)")
print(f"Max Drawdown        : {max_drawdown:.2f}%")
print(f"----------------------------------------------------------")
print(f"Starting Balance    : ${STARTING_BALANCE:,.2f}")
print(f"Final Balance       : ${account_balance:,.2f}")
print(f"Total Return        : {total_return:.2f}%")
print(f"==========================================================")

# --- 6. INTERACTIVE VISUALIZATION (PLOTLY) ---
fig = make_subplots(
    rows=4, cols=1, 
    shared_xaxes=True, 
    vertical_spacing=0.05,
    row_heights=[0.25, 0.15, 0.45, 0.15],
    subplot_titles=("Equity Curve", "Trade PnL", "Price Action & Executions", "Z-Score Oscillator")
)

# Panel 1: Compounding Equity Curve
fig.add_trace(go.Scatter(x=results_df.index, y=results_df['Equity'], line=dict(color='blue', width=2), name="Equity"), row=1, col=1)

# Panel 2: Profit/Loss Scatter Plot
if total_trades > 0:
    win_times = [t['Exit_Time'] for t in trades_log if t['Win']]
    win_pnls = [t['PnL'] for t in trades_log if t['Win']]
    lose_times = [t['Exit_Time'] for t in trades_log if not t['Win']]
    lose_pnls = [t['PnL'] for t in trades_log if not t['Win']]
    
    fig.add_trace(go.Scatter(x=win_times, y=win_pnls, mode='markers', marker=dict(color='green', symbol='triangle-up', size=8), name="Win PnL"), row=2, col=1)
    fig.add_trace(go.Scatter(x=lose_times, y=lose_pnls, mode='markers', marker=dict(color='red', symbol='triangle-down', size=8), name="Loss PnL"), row=2, col=1)

# Panel 3: Price Action with Reverting Mean
fig.add_trace(go.Scatter(x=df.index, y=df['Close'], line=dict(color='black', width=1), name="Close Price"), row=3, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df['Mean'], line=dict(color='orange', width=1.5), name="Mean (20)"), row=3, col=1)

if total_trades > 0:
    long_entries = [t['Entry_Time'] for t in trades_log if t['Direction'] == 1]
    long_prices = [t['Entry_Price'] for t in trades_log if t['Direction'] == 1]
    short_entries = [t['Entry_Time'] for t in trades_log if t['Direction'] == -1]
    short_prices = [t['Entry_Price'] for t in trades_log if t['Direction'] == -1]
    
    fig.add_trace(go.Scatter(x=long_entries, y=long_prices, mode='markers', marker=dict(color='lime', symbol='triangle-up', size=10, line=dict(width=1, color='black')), name="Long Entry"), row=3, col=1)
    fig.add_trace(go.Scatter(x=short_entries, y=short_prices, mode='markers', marker=dict(color='magenta', symbol='triangle-down', size=10, line=dict(width=1, color='black')), name="Short Entry"), row=3, col=1)

# Panel 4: Z-Score Statistical Oscillator
fig.add_trace(go.Scatter(x=df.index, y=df['ZScore'], line=dict(color='purple', width=1), name="Z-Score"), row=4, col=1)
fig.add_hline(y=1.5, line_dash="dash", line_color="red", row=4, col=1)
fig.add_hline(y=-1.5, line_dash="dash", line_color="green", row=4, col=1)
fig.add_hline(y=0, line_color="black", row=4, col=1)

fig.update_layout(
    title=f"Statistical Arbitrage: Asian Session Mean Reversion | {SYMBOL}",
    height=900,
    showlegend=False,
    hovermode="x unified",
    dragmode="zoom"
)

# Export interactive HTML report
fig.write_html("algorithmic_backtest_report.html", auto_open=True)
