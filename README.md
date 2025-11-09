# RobinHood Trading Bots

A collection of automated trading bots for Robinhood using technical indicators.

## Available Bots

### 1. RSI Trading Bot (`RobinhoodBot.py`)
- Uses RSI (Relative Strength Index) indicator
- Buys when RSI <= 30 (oversold)
- Sells when RSI >= 70 (overbought)
- Includes support and resistance levels

### 2. MACD Trading Bot (`RobinhoodMACDBot.py`) - **NEW!**
- Uses MACD (Moving Average Convergence Divergence) indicator
- Buys on bullish crossover (MACD crosses above signal line)
- Sells on bearish crossover (MACD crosses below signal line)
- **1% daily profit target** with automatic exit
- **0.5% stop loss** protection
- PDT (Pattern Day Trader) rule compliance
- Transaction tracking and logging
- Small position sizing (< $20 per trade)

---

## MACD Trading Bot - Detailed Guide

### Features

- **MACD Strategy**: Trades based on MACD crossover signals
- **Profit Targets**: Automatically exits at 1% profit (configurable)
- **Stop Loss**: Protects capital with -0.5% stop loss (configurable)
- **Account Tracking**: Monitors actual buying power and portfolio value from Robinhood
- **Position Verification**: Verifies ownership before selling to prevent errors
- **Smart Position Sizing**: Uses minimum of max_investment and available buying power
- **PDT Protection**: Enforces max 3 day trades in 5 trading days
- **Transaction Logging**: Saves all trades to JSON file
- **Real-time Monitoring**: Displays current P/L, account balance, and position status
- **Small Positions**: Invests < $20 per trade for risk management
- **Volatile Assets**: Targets TQQQ (3x leveraged QQQ) by default

### How MACD Works

The MACD indicator consists of:
- **MACD Line**: 12-period EMA - 26-period EMA
- **Signal Line**: 9-period EMA of MACD line
- **Histogram**: MACD line - Signal line

**Buy Signal**: MACD line crosses above signal line (bullish)
**Sell Signal**: MACD line crosses below signal line (bearish)

### Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Configure the bot:
Edit `RobinhoodMACDBot.py` and update the CONFIG dictionary:
```python
CONFIG = {
    'username': 'your_robinhood_username',
    'password': 'your_robinhood_password',
    'symbol': 'TQQQ',  # Change to your preferred symbol
    'max_investment': 20.00,
    'profit_target': 1.0,  # 1% profit target
    'stop_loss': -0.5,  # 0.5% stop loss
    # ... other settings
}
```

### Usage

**Quick Start - Foreground:**
```bash
python RobinhoodMACDBot.py
```

**Run Continuously in Background (Recommended):**
```bash
# Make startup script executable
chmod +x start_bot.sh

# Run in background with auto-restart
./start_bot.sh background

# View logs
tail -f logs/macd_bot_*.log
```

**For production deployment**, see **[DEPLOYMENT.md](DEPLOYMENT.md)** for complete guide on:
- Systemd service (Linux) - auto-starts on boot
- Docker container - isolated and portable
- Screen/Tmux sessions - simple terminal management
- Auto-restart on crashes
- Monitoring and alerts

The bot will:
1. Login to Robinhood (prompts for 2FA if enabled)
2. Display current configuration and trading summary
3. **Monitor MACD continuously** every 5 minutes (24/7 operation)
4. Execute trades automatically based on MACD signals
5. Exit positions at profit target or stop loss
6. Log all transactions to `transactions.json`
7. Save logs to `logs/` directory for monitoring

### Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `symbol` | TQQQ | Stock/ETF symbol to trade |
| `max_investment` | 20.00 | Maximum $ per trade |
| `profit_target` | 1.0 | Target profit % before selling |
| `stop_loss` | -0.5 | Stop loss % to limit losses |
| `macd_fast` | 12 | MACD fast EMA period |
| `macd_slow` | 26 | MACD slow EMA period |
| `macd_signal` | 9 | MACD signal line period |
| `check_interval` | 300 | Seconds between checks |
| `max_day_trades` | 3 | Max day trades in 5 days (PDT) |
| `log_to_file` | True | Enable file logging for background operation |
| `log_directory` | logs | Directory for log files |
| `log_rotation_type` | time | Log rotation: 'time' (daily) or 'size' |
| `log_backup_count` | 30 | Number of backup logs to keep |
| `log_compress_archives` | True | Compress old logs with gzip (saves 90% space) |
| `log_retention_days` | 90 | Delete logs older than N days |

### Log Management

The bot includes **automatic log management** to prevent disk space issues:

- **Automatic rotation**: Daily (or by size)
- **Automatic compression**: Gzip old logs (saves ~90% space)
- **Automatic cleanup**: Deletes logs older than 90 days
- **Disk space**: ~6-18 MB for normal operation (90 days)

**Quick commands:**
```bash
# List all logs with sizes
./manage_logs.py list

# Analyze disk usage
./manage_logs.py analyze

# View recent activity
tail -f logs/macd_bot.log

# Cleanup old logs
./manage_logs.py cleanup --days 30
```

For complete log management guide, see **[LOG_MANAGEMENT.md](LOG_MANAGEMENT.md)**.

### Recommended Symbols

For volatility and small positions, consider:
- **TQQQ** - 3x leveraged QQQ (tech-heavy)
- **SQQQ** - 3x inverse QQQ (profits from tech decline)
- **SPXL** - 3x leveraged S&P 500
- **TNA** - 3x leveraged Russell 2000
- Individual volatile stocks: TSLA, AMD, NVDA, etc.

**Warning**: 3x leveraged ETFs are highly volatile and risky!

### Pattern Day Trader (PDT) Rule

The bot enforces PDT compliance:
- Tracks all trades in last 5 trading days
- Prevents 4th day trade (buying and selling same day)
- Allows selling next day even if it would exceed 3 trades
- Displays current day trade count in real-time

If you have > $25k in your account, PDT doesn't apply.

### Transaction Log

All trades are saved to `transactions.json`:
```json
{
  "transactions": [
    {
      "type": "BUY",
      "symbol": "TQQQ",
      "quantity": 3,
      "price": 65.50,
      "total_cost": 196.50,
      "timestamp": "2025-11-09T10:30:00",
      "order_id": "abc123"
    },
    {
      "type": "SELL",
      "symbol": "TQQQ",
      "quantity": 3,
      "price": 66.16,
      "total_proceeds": 198.48,
      "profit_loss": 1.98,
      "profit_loss_pct": 1.01,
      "timestamp": "2025-11-09T14:15:00"
    }
  ],
  "current_position": null,
  "day_trades": []
}
```

### Example Output

```
============================================================
ROBINHOOD MACD TRADING BOT
============================================================
Symbol: TQQQ
Max Investment: $20.0
MACD Parameters: Fast=12, Slow=26, Signal=9
Check Interval: 300 seconds
PDT Protection: Max 3 day trades in 5 trading days
============================================================

============================================================
[2025-11-09 10:30:15] TQQQ - Price: $65.50
MACD: 0.1234 | Signal: 0.0987 | Histogram: 0.0247
Account - Buying Power: $1523.45 | Portfolio: $2450.00 | Cash: $1523.45
Position: NONE
Day Trades: 0/3 (last 5 days)
============================================================

[2025-11-09 10:30:15] 🔔 BULLISH CROSSOVER DETECTED!
[2025-11-09 10:30:15] Calculated position: 3 shares = $19.65
[2025-11-09 10:30:16] BUYING 3 shares of TQQQ at $65.50
[2025-11-09 10:30:17] BUY ORDER PLACED: 3 shares @ $65.50 = $196.50

...

[2025-11-09 14:15:20] 🎯 PROFIT TARGET REACHED: 1.01% (Target: 1.0%)
[2025-11-09 14:15:21] SELLING 3 shares of TQQQ at $66.16
[2025-11-09 14:15:22] SELL ORDER PLACED: 3 shares @ $66.16 = $198.48
[2025-11-09 14:15:22] PROFIT/LOSS: $1.98 (+1.01%)
```

### Safety Features

1. **Buying Power Verification**: Checks actual account funds before placing orders
2. **Position Verification**: Verifies ownership before selling to prevent errors
3. **Position Limits**: Never invests more than configured max or available buying power
4. **PDT Protection**: Prevents violation of day trading rules
5. **Stop Loss**: Limits losses to configured percentage (0.5% per transaction)
6. **Profit Target**: Locks in gains automatically (1% per transaction)
7. **Transaction Logging**: Complete audit trail
8. **Error Handling**: Graceful failure on API errors

### Risks and Disclaimers

- **High Risk**: Algorithmic trading carries significant risk
- **No Guarantees**: Past performance doesn't guarantee future results
- **Leveraged ETFs**: Extra risky due to volatility decay
- **Use at Your Own Risk**: Author not responsible for losses
- **Start Small**: Test with minimal amounts first
- **Paper Trade**: Consider simulated trading before live

### Tips for Success

1. **Start Small**: Use $5-10 per trade initially
2. **Monitor Closely**: Check the bot regularly
3. **Review Logs**: Analyze your transaction history
4. **Adjust Parameters**: Tune MACD periods for your symbol
5. **Backtest**: Test strategy on historical data first
6. **Market Hours**: Bot works best during market hours (9:30 AM - 4:00 PM ET)
7. **Avoid News Events**: Disable during major economic announcements

### Troubleshooting

**Bot not buying/selling**:
- Check if MACD crossover occurred
- Verify sufficient data (needs 26+ periods)
- Check PDT limit not reached

**Login fails**:
- Verify username/password
- Complete 2FA prompt
- Check Robinhood account status

**Transaction log errors**:
- Ensure write permissions in directory
- Check disk space
- Verify JSON format not corrupted

### Future Enhancements

Potential improvements:
- [ ] Backtesting framework
- [ ] Multiple symbol support
- [ ] Web dashboard
- [ ] Email/SMS notifications
- [ ] Advanced risk management
- [ ] Machine learning integration
- [ ] Support for options trading

---

## Original RSI Bot

See `RobinhoodBot.py` for the original RSI-based trading bot.

---

## Support

For issues or questions:
- Create an issue on GitHub
- Review Robinhood API documentation
- Join trading bot communities

**Remember**: Only invest what you can afford to lose!
