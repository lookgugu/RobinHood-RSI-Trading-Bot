"""
Robinhood MACD Trading Bot

This bot uses the MACD (Moving Average Convergence Divergence) indicator
to make trading decisions on volatile assets. It includes:
- MACD crossover strategy
- Pattern Day Trader (PDT) rule compliance
- Transaction logging and tracking
- Position sizing under $20
- Automatic trade management
"""

from pyrh import Robinhood
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import tulipy as ti
import sched
import time
import json
import os
import sys
import logging
from collections import deque

# Configuration
CONFIG = {
    'username': 'your_username',  # Replace with your username
    'password': 'your_password',  # Replace with your password
    'symbol': 'TQQQ',  # Volatile ETF - ProShares UltraPro QQQ (3x leveraged)
    'max_investment': 20.00,  # Maximum investment per trade
    'profit_target': 1.0,  # Target profit percentage (1% = 1.0)
    'stop_loss': -0.5,  # Stop loss percentage (-0.5% = -0.5)
    'macd_fast': 12,  # MACD fast period
    'macd_slow': 26,  # MACD slow period
    'macd_signal': 9,  # MACD signal period
    'check_interval': 300,  # Check every 5 minutes (300 seconds)
    'data_interval': '5minute',  # Data interval
    'data_span': 'day',  # Data span
    'transaction_log': 'transactions.json',  # Transaction log file
    'pdt_tracking_days': 5,  # PDT rule: track last 5 trading days
    'max_day_trades': 3,  # PDT rule: max 3 day trades in 5 trading days
    'use_profit_target': True,  # Enable profit target exit
    'use_stop_loss': True,  # Enable stop loss exit
    'log_to_file': True,  # Enable file logging for background operation
    'log_directory': 'logs',  # Directory for log files
}

class MACDTradingBot:
    def __init__(self, config):
        self.config = config
        self.rh = Robinhood()
        self.entered_trade = False
        self.current_position = None
        self.transactions = []
        self.day_trades = deque(maxlen=100)  # Keep track of recent day trades
        self.scheduler = sched.scheduler(time.time, time.sleep)

        # Setup logging
        self.setup_logging()

        # Load existing transaction history
        self.load_transactions()

    def setup_logging(self):
        """Setup logging for file output or console"""
        if self.config.get('log_to_file', False):
            # Create logs directory if it doesn't exist
            log_dir = self.config.get('log_directory', 'logs')
            os.makedirs(log_dir, exist_ok=True)

            # Setup file logging
            log_file = os.path.join(log_dir, f"macd_bot_{datetime.now().strftime('%Y%m%d')}.log")
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_file),
                    logging.StreamHandler(sys.stdout)  # Also output to console
                ]
            )
            logging.info("Logging initialized - output to file and console")
        else:
            # Console only
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[logging.StreamHandler(sys.stdout)]
            )

    def log(self, message, level='info'):
        """Log a message with timestamp"""
        timestamp = f"[{datetime.now()}]"
        full_message = f"{timestamp} {message}"

        # Use logging module
        if level == 'error':
            logging.error(message)
        elif level == 'warning':
            logging.warning(message)
        else:
            logging.info(message)

        # Also print to console for immediate feedback
        if not self.config.get('log_to_file', False):
            print(full_message)

    def login(self):
        """Log in to Robinhood (will prompt for 2FA if enabled)"""
        try:
            self.rh.login(
                username=self.config['username'],
                password=self.config['password']
            )
            print(f"[{datetime.now()}] Successfully logged in to Robinhood")
            return True
        except Exception as e:
            print(f"[{datetime.now()}] Login failed: {e}")
            return False

    def get_buying_power(self):
        """Get available buying power from Robinhood account"""
        try:
            account_data = self.rh.get_account()
            if account_data and 'buying_power' in account_data:
                buying_power = float(account_data['buying_power'])
                return buying_power
            else:
                print(f"[{datetime.now()}] Warning: Could not retrieve buying power")
                return None
        except Exception as e:
            print(f"[{datetime.now()}] Error getting buying power: {e}")
            return None

    def get_account_info(self):
        """Get account information including buying power and portfolio value"""
        try:
            account_data = self.rh.get_account()
            if account_data:
                info = {
                    'buying_power': float(account_data.get('buying_power', 0)),
                    'portfolio_value': float(account_data.get('portfolio_value', 0)),
                    'cash': float(account_data.get('cash', 0)),
                }
                return info
            return None
        except Exception as e:
            print(f"[{datetime.now()}] Error getting account info: {e}")
            return None

    def get_current_positions(self):
        """Get current positions from Robinhood"""
        try:
            positions = self.rh.positions()
            if positions and 'results' in positions:
                holdings = {}
                for position in positions['results']:
                    quantity = float(position.get('quantity', 0))
                    if quantity > 0:
                        instrument_url = position.get('instrument')
                        # Get instrument details to find symbol
                        instrument = self.rh.get_url(instrument_url)
                        if instrument:
                            symbol = instrument.get('symbol')
                            holdings[symbol] = {
                                'quantity': quantity,
                                'average_buy_price': float(position.get('average_buy_price', 0))
                            }
                return holdings
            return {}
        except Exception as e:
            print(f"[{datetime.now()}] Error getting positions: {e}")
            return {}

    def load_transactions(self):
        """Load transaction history from file"""
        if os.path.exists(self.config['transaction_log']):
            try:
                with open(self.config['transaction_log'], 'r') as f:
                    data = json.load(f)
                    self.transactions = data.get('transactions', [])
                    self.day_trades = deque(data.get('day_trades', []), maxlen=100)
                    self.current_position = data.get('current_position', None)
                    self.entered_trade = self.current_position is not None
                print(f"[{datetime.now()}] Loaded {len(self.transactions)} transactions")
            except Exception as e:
                print(f"[{datetime.now()}] Error loading transactions: {e}")

    def save_transactions(self):
        """Save transaction history to file"""
        try:
            data = {
                'transactions': self.transactions,
                'day_trades': list(self.day_trades),
                'current_position': self.current_position,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.config['transaction_log'], 'w') as f:
                json.dump(data, f, indent=2)
            print(f"[{datetime.now()}] Saved transactions to {self.config['transaction_log']}")
        except Exception as e:
            print(f"[{datetime.now()}] Error saving transactions: {e}")

    def is_trading_day(self, date):
        """Check if a given date is a trading day (weekday)"""
        return date.weekday() < 5  # Monday=0, Friday=4

    def count_recent_day_trades(self):
        """Count day trades in the last 5 trading days"""
        if not self.day_trades:
            return 0

        today = datetime.now()
        trading_days_back = 0
        current_date = today
        cutoff_date = None

        # Find the date 5 trading days ago
        while trading_days_back < self.config['pdt_tracking_days']:
            current_date -= timedelta(days=1)
            if self.is_trading_day(current_date):
                trading_days_back += 1

        cutoff_date = current_date

        # Count day trades after cutoff date
        recent_trades = [
            dt for dt in self.day_trades
            if datetime.fromisoformat(dt['date']) >= cutoff_date
        ]

        return len(recent_trades)

    def can_day_trade(self):
        """Check if we can make a day trade without violating PDT rule"""
        recent_day_trades = self.count_recent_day_trades()
        can_trade = recent_day_trades < self.config['max_day_trades']

        if not can_trade:
            print(f"[{datetime.now()}] PDT RULE: Already made {recent_day_trades} day trades in last 5 trading days. Cannot day trade.")

        return can_trade

    def record_day_trade(self, buy_date, sell_date):
        """Record a day trade"""
        buy_dt = datetime.fromisoformat(buy_date)
        sell_dt = datetime.fromisoformat(sell_date)

        # Check if it's actually a day trade (same trading day)
        if buy_dt.date() == sell_dt.date():
            day_trade_record = {
                'date': sell_date,
                'symbol': self.config['symbol'],
                'buy_time': buy_date,
                'sell_time': sell_date
            }
            self.day_trades.append(day_trade_record)
            print(f"[{datetime.now()}] DAY TRADE RECORDED: {self.count_recent_day_trades()}/{self.config['max_day_trades']} in last 5 days")

    def calculate_macd(self, close_prices):
        """Calculate MACD indicator"""
        try:
            data = np.array(close_prices, dtype=np.float64)

            # Calculate MACD using tulipy
            macd, macd_signal, macd_histogram = ti.macd(
                data,
                short_period=self.config['macd_fast'],
                long_period=self.config['macd_slow'],
                signal_period=self.config['macd_signal']
            )

            return {
                'macd': macd,
                'signal': macd_signal,
                'histogram': macd_histogram
            }
        except Exception as e:
            print(f"[{datetime.now()}] Error calculating MACD: {e}")
            return None

    def get_historical_data(self):
        """Get historical price data from Robinhood"""
        try:
            print(f"[{datetime.now()}] Fetching historical data for {self.config['symbol']}")
            historical_quotes = self.rh.get_historical_quotes(
                self.config['symbol'],
                self.config['data_interval'],
                self.config['data_span']
            )

            if not historical_quotes or 'results' not in historical_quotes:
                print(f"[{datetime.now()}] No historical data received")
                return None

            close_prices = []
            timestamps = []

            for item in historical_quotes['results'][0]['historicals']:
                close_prices.append(float(item['close_price']))
                timestamps.append(item['begins_at'])

            return {
                'close_prices': close_prices,
                'timestamps': timestamps,
                'current_price': close_prices[-1] if close_prices else None
            }
        except Exception as e:
            print(f"[{datetime.now()}] Error fetching historical data: {e}")
            return None

    def calculate_position_size(self, current_price, buying_power=None):
        """Calculate number of shares to buy based on max investment and available buying power"""
        if current_price <= 0:
            return 0, 0

        # Determine the maximum amount to invest
        max_to_invest = self.config['max_investment']

        # If buying power is provided, use the minimum of max_investment and buying_power
        if buying_power is not None:
            max_to_invest = min(max_to_invest, buying_power)

        # Calculate shares
        max_shares = int(max_to_invest / current_price)
        shares = max(1, max_shares) if max_to_invest >= current_price else 0

        # Calculate actual investment amount
        actual_investment = shares * current_price

        return shares, actual_investment

    def place_buy_order(self, instrument, quantity, price):
        """Place a buy order"""
        try:
            print(f"[{datetime.now()}] BUYING {quantity} shares of {self.config['symbol']} at ${price:.2f}")

            # Place the order
            order = self.rh.place_buy_order(instrument, quantity)

            # Record the transaction
            transaction = {
                'type': 'BUY',
                'symbol': self.config['symbol'],
                'quantity': quantity,
                'price': price,
                'total_cost': quantity * price,
                'timestamp': datetime.now().isoformat(),
                'order_id': order.get('id') if order else 'unknown'
            }

            self.transactions.append(transaction)
            self.current_position = transaction
            self.entered_trade = True
            self.save_transactions()

            print(f"[{datetime.now()}] BUY ORDER PLACED: {quantity} shares @ ${price:.2f} = ${quantity * price:.2f}")
            return True
        except Exception as e:
            print(f"[{datetime.now()}] Error placing buy order: {e}")
            return False

    def place_sell_order(self, instrument, quantity, price):
        """Place a sell order"""
        try:
            # Verify we own the position
            positions = self.get_current_positions()
            if self.config['symbol'] not in positions:
                print(f"[{datetime.now()}] ERROR: No {self.config['symbol']} position found in account. Cannot sell.")
                return False

            owned_quantity = positions[self.config['symbol']]['quantity']
            if owned_quantity < quantity:
                print(f"[{datetime.now()}] WARNING: Trying to sell {quantity} shares but only own {owned_quantity}. Adjusting quantity.")
                quantity = int(owned_quantity)

            if quantity <= 0:
                print(f"[{datetime.now()}] ERROR: No shares to sell.")
                return False

            print(f"[{datetime.now()}] SELLING {quantity} shares of {self.config['symbol']} at ${price:.2f}")

            # Place the order
            order = self.rh.place_sell_order(instrument, quantity)

            # Calculate profit/loss
            buy_price = self.current_position['price'] if self.current_position else price
            profit_loss = (price - buy_price) * quantity
            profit_loss_pct = ((price - buy_price) / buy_price * 100) if buy_price > 0 else 0

            # Record the transaction
            transaction = {
                'type': 'SELL',
                'symbol': self.config['symbol'],
                'quantity': quantity,
                'price': price,
                'total_proceeds': quantity * price,
                'timestamp': datetime.now().isoformat(),
                'order_id': order.get('id') if order else 'unknown',
                'profit_loss': profit_loss,
                'profit_loss_pct': profit_loss_pct
            }

            self.transactions.append(transaction)

            # Check if this is a day trade
            if self.current_position:
                self.record_day_trade(
                    self.current_position['timestamp'],
                    transaction['timestamp']
                )

            self.current_position = None
            self.entered_trade = False
            self.save_transactions()

            print(f"[{datetime.now()}] SELL ORDER PLACED: {quantity} shares @ ${price:.2f} = ${quantity * price:.2f}")
            print(f"[{datetime.now()}] PROFIT/LOSS: ${profit_loss:.2f} ({profit_loss_pct:+.2f}%)")
            return True
        except Exception as e:
            print(f"[{datetime.now()}] Error placing sell order: {e}")
            return False

    def run_strategy(self, sc):
        """Main trading strategy execution"""
        try:
            # Get account info and buying power
            account_info = self.get_account_info()
            buying_power = account_info['buying_power'] if account_info else None

            # Get historical data
            data = self.get_historical_data()
            if not data or len(data['close_prices']) < self.config['macd_slow'] + self.config['macd_signal']:
                print(f"[{datetime.now()}] Insufficient data for MACD calculation")
                self.scheduler.enter(self.config['check_interval'], 1, self.run_strategy, (sc,))
                return

            # Calculate MACD
            macd_data = self.calculate_macd(data['close_prices'])
            if not macd_data:
                print(f"[{datetime.now()}] MACD calculation failed")
                self.scheduler.enter(self.config['check_interval'], 1, self.run_strategy, (sc,))
                return

            current_price = data['current_price']
            current_macd = macd_data['macd'][-1]
            current_signal = macd_data['signal'][-1]
            current_histogram = macd_data['histogram'][-1]

            # Previous values for crossover detection
            prev_macd = macd_data['macd'][-2] if len(macd_data['macd']) > 1 else current_macd
            prev_signal = macd_data['signal'][-2] if len(macd_data['signal']) > 1 else current_signal

            print(f"\n{'='*60}")
            print(f"[{datetime.now()}] {self.config['symbol']} - Price: ${current_price:.2f}")
            print(f"MACD: {current_macd:.4f} | Signal: {current_signal:.4f} | Histogram: {current_histogram:.4f}")

            # Display account info
            if account_info:
                print(f"Account - Buying Power: ${buying_power:.2f} | Portfolio: ${account_info['portfolio_value']:.2f} | Cash: ${account_info['cash']:.2f}")
            else:
                print(f"Account - Buying Power: N/A (using max investment: ${self.config['max_investment']})")

            # Display position and P/L
            if self.entered_trade and self.current_position:
                buy_price = self.current_position['price']
                quantity = self.current_position['quantity']
                current_pl = (current_price - buy_price) * quantity
                current_pl_pct = ((current_price - buy_price) / buy_price) * 100
                print(f"Position: HOLDING {quantity} shares @ ${buy_price:.2f}")
                print(f"Current P/L: ${current_pl:.2f} ({current_pl_pct:+.2f}%) | Target: {self.config['profit_target']}% | Stop: {self.config['stop_loss']}%")
            else:
                print(f"Position: NONE")

            print(f"Day Trades: {self.count_recent_day_trades()}/{self.config['max_day_trades']} (last 5 days)")
            print(f"{'='*60}\n")

            # Get instrument
            instrument = self.rh.instruments(self.config['symbol'])[0]

            # First, check if we need to exit based on profit target or stop loss
            if self.entered_trade:
                should_exit, exit_reason = self.check_profit_target(current_price)
                if should_exit:
                    if self.can_day_trade() or self.is_not_day_trade():
                        quantity = self.current_position['quantity'] if self.current_position else 1
                        self.place_sell_order(instrument, quantity, current_price)
                        self.scheduler.enter(self.config['check_interval'], 1, self.run_strategy, (sc,))
                        return
                    else:
                        print(f"[{datetime.now()}] ⚠️  Cannot exit ({exit_reason}) - would violate PDT rule. Holding position.")

            # BUY SIGNAL: MACD crosses above signal line (bullish crossover)
            if prev_macd <= prev_signal and current_macd > current_signal and not self.entered_trade:
                print(f"[{datetime.now()}] 🔔 BULLISH CROSSOVER DETECTED!")
                quantity, investment_amount = self.calculate_position_size(current_price, buying_power)

                if quantity > 0:
                    if buying_power is not None and investment_amount > buying_power:
                        print(f"[{datetime.now()}] Insufficient buying power: ${buying_power:.2f} < ${investment_amount:.2f}")
                    else:
                        print(f"[{datetime.now()}] Calculated position: {quantity} shares = ${investment_amount:.2f}")
                        self.place_buy_order(instrument, quantity, current_price)
                else:
                    print(f"[{datetime.now()}] Insufficient funds to buy even 1 share at ${current_price:.2f}")

            # SELL SIGNAL: MACD crosses below signal line (bearish crossover)
            elif prev_macd >= prev_signal and current_macd < current_signal and self.entered_trade:
                print(f"[{datetime.now()}] 🔔 BEARISH CROSSOVER DETECTED!")

                # Check PDT rule before selling
                if self.can_day_trade() or self.is_not_day_trade():
                    quantity = self.current_position['quantity'] if self.current_position else 1
                    self.place_sell_order(instrument, quantity, current_price)
                else:
                    print(f"[{datetime.now()}] ⚠️  Cannot sell - would violate PDT rule. Holding position.")

        except Exception as e:
            print(f"[{datetime.now()}] Error in strategy execution: {e}")

        # Schedule next run
        self.scheduler.enter(self.config['check_interval'], 1, self.run_strategy, (sc,))

    def is_not_day_trade(self):
        """Check if selling now would NOT be a day trade"""
        if not self.current_position:
            return True

        buy_time = datetime.fromisoformat(self.current_position['timestamp'])
        current_time = datetime.now()

        return buy_time.date() != current_time.date()

    def check_profit_target(self, current_price):
        """Check if profit target or stop loss has been reached"""
        if not self.current_position:
            return False, None

        buy_price = self.current_position['price']
        profit_pct = ((current_price - buy_price) / buy_price) * 100

        # Check profit target
        if self.config['use_profit_target'] and profit_pct >= self.config['profit_target']:
            print(f"[{datetime.now()}] 🎯 PROFIT TARGET REACHED: {profit_pct:.2f}% (Target: {self.config['profit_target']}%)")
            return True, 'PROFIT_TARGET'

        # Check stop loss
        if self.config['use_stop_loss'] and profit_pct <= self.config['stop_loss']:
            print(f"[{datetime.now()}] 🛑 STOP LOSS TRIGGERED: {profit_pct:.2f}% (Stop: {self.config['stop_loss']}%)")
            return True, 'STOP_LOSS'

        return False, None

    def print_summary(self):
        """Print trading summary"""
        print("\n" + "="*60)
        print("TRADING SUMMARY")
        print("="*60)
        print(f"Total Transactions: {len(self.transactions)}")

        total_profit = sum(t.get('profit_loss', 0) for t in self.transactions if t['type'] == 'SELL')
        print(f"Total Profit/Loss: ${total_profit:.2f}")

        wins = sum(1 for t in self.transactions if t['type'] == 'SELL' and t.get('profit_loss', 0) > 0)
        losses = sum(1 for t in self.transactions if t['type'] == 'SELL' and t.get('profit_loss', 0) < 0)
        print(f"Wins: {wins} | Losses: {losses}")

        if wins + losses > 0:
            win_rate = wins / (wins + losses) * 100
            print(f"Win Rate: {win_rate:.1f}%")

        print(f"Day Trades (last 5 days): {self.count_recent_day_trades()}/{self.config['max_day_trades']}")
        print("="*60 + "\n")

    def start(self):
        """Start the trading bot"""
        print("\n" + "="*60)
        print("ROBINHOOD MACD TRADING BOT")
        print("="*60)
        print(f"Symbol: {self.config['symbol']}")
        print(f"Max Investment: ${self.config['max_investment']}")
        print(f"MACD Parameters: Fast={self.config['macd_fast']}, Slow={self.config['macd_slow']}, Signal={self.config['macd_signal']}")
        print(f"Check Interval: {self.config['check_interval']} seconds")
        print(f"PDT Protection: Max {self.config['max_day_trades']} day trades in {self.config['pdt_tracking_days']} trading days")
        print("="*60 + "\n")

        if not self.login():
            print("Failed to login. Exiting.")
            return

        self.print_summary()

        print(f"[{datetime.now()}] Bot started. Monitoring {self.config['symbol']}...")
        print("Press Ctrl+C to stop.\n")

        # Start the scheduler
        self.scheduler.enter(1, 1, self.run_strategy, (self.scheduler,))

        try:
            self.scheduler.run()
        except KeyboardInterrupt:
            print("\n\n" + "="*60)
            print("BOT STOPPED")
            print("="*60)
            self.print_summary()
            print("Goodbye!")

if __name__ == "__main__":
    print("""
    ⚠️  IMPORTANT: Before running this bot, please:

    1. Update CONFIG dictionary with your Robinhood credentials
    2. Review the symbol (TQQQ is a volatile 3x leveraged ETF)
    3. Ensure you understand the risks of algorithmic trading
    4. Start with paper trading or very small amounts
    5. The bot respects PDT rules (max 3 day trades in 5 trading days)

    Press Enter to continue or Ctrl+C to exit...
    """)
    input()

    bot = MACDTradingBot(CONFIG)
    bot.start()
