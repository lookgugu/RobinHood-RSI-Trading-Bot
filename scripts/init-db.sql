-- Initialize Trading Bot Database

-- Create trades table
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    trade_type VARCHAR(10) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    quantity INTEGER NOT NULL,
    price DECIMAL(12, 4) NOT NULL,
    total_value DECIMAL(12, 4) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    order_id VARCHAR(100),
    status VARCHAR(20) DEFAULT 'EXECUTED',
    profit_loss DECIMAL(12, 4),
    profit_loss_pct DECIMAL(8, 4),
    strategy VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create positions table
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    quantity INTEGER NOT NULL DEFAULT 0,
    average_cost DECIMAL(12, 4) NOT NULL,
    current_price DECIMAL(12, 4),
    unrealized_pnl DECIMAL(12, 4),
    unrealized_pnl_pct DECIMAL(8, 4),
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create day_trades table for PDT tracking
CREATE TABLE IF NOT EXISTS day_trades (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    buy_time TIMESTAMP WITH TIME ZONE NOT NULL,
    sell_time TIMESTAMP WITH TIME ZONE NOT NULL,
    quantity INTEGER NOT NULL,
    buy_price DECIMAL(12, 4) NOT NULL,
    sell_price DECIMAL(12, 4) NOT NULL,
    profit_loss DECIMAL(12, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create orders table
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(100),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) DEFAULT 'MARKET',
    quantity INTEGER NOT NULL,
    limit_price DECIMAL(12, 4),
    stop_price DECIMAL(12, 4),
    status VARCHAR(20) DEFAULT 'PENDING',
    filled_quantity INTEGER DEFAULT 0,
    filled_price DECIMAL(12, 4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create portfolio_summary table
CREATE TABLE IF NOT EXISTS portfolio_summary (
    id SERIAL PRIMARY KEY,
    total_value DECIMAL(12, 4) NOT NULL,
    cash_balance DECIMAL(12, 4) NOT NULL,
    total_invested DECIMAL(12, 4) NOT NULL,
    total_pnl DECIMAL(12, 4) NOT NULL,
    total_pnl_pct DECIMAL(8, 4),
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_day_trades_date ON day_trades(trade_date);
CREATE INDEX IF NOT EXISTS idx_day_trades_symbol ON day_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_external_id ON orders(external_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);

-- Create view for recent day trades count
CREATE OR REPLACE VIEW recent_day_trades AS
SELECT
    COUNT(*) as trade_count,
    trade_date
FROM day_trades
WHERE trade_date >= CURRENT_DATE - INTERVAL '5 days'
GROUP BY trade_date
ORDER BY trade_date DESC;

-- Create view for portfolio P&L summary
CREATE OR REPLACE VIEW portfolio_pnl AS
SELECT
    symbol,
    SUM(CASE WHEN trade_type = 'BUY' THEN total_value ELSE 0 END) as total_bought,
    SUM(CASE WHEN trade_type = 'SELL' THEN total_value ELSE 0 END) as total_sold,
    SUM(CASE WHEN trade_type = 'SELL' THEN profit_loss ELSE 0 END) as realized_pnl,
    COUNT(*) as total_trades
FROM trades
WHERE status = 'EXECUTED'
GROUP BY symbol;
