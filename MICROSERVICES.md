# Trading Bot Microservices Architecture

This document describes the microservices architecture for the Robinhood Trading Bot.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TRADING BOT MICROSERVICES                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  GATEWAY    │────│   MARKET    │────│  STRATEGY   │────│  EXECUTION  │  │
│  │   :8000     │    │    DATA     │    │   ENGINE    │    │   :8003     │  │
│  │             │    │   :8001     │    │   :8002     │    │             │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│         │                  │                  │                  │          │
│         ▼                  ▼                  ▼                  ▼          │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         Redis (Pub/Sub + Cache)                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│         │                  │                  │                  │          │
│         ▼                  ▼                  ▼                  ▼          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                     │
│  │    RISK     │    │ COMPLIANCE  │    │  PORTFOLIO  │                     │
│  │  MANAGEMENT │    │   (PDT)     │    │   :8006     │                     │
│  │   :8004     │    │   :8005     │    │             │                     │
│  └─────────────┘    └─────────────┘    └─────────────┘                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Services

### 1. Gateway Service (Port 8000)
**Responsibility**: Authentication and API routing

- Robinhood authentication
- Session management
- Health checks

**Endpoints**:
- `POST /auth/login` - Login to Robinhood
- `POST /auth/logout` - Logout
- `GET /auth/status` - Check auth status
- `GET /health` - Health check

### 2. Market Data Service (Port 8001)
**Responsibility**: Price data fetching and caching

- Historical OHLCV data
- Real-time quotes
- Price caching with Redis

**Endpoints**:
- `GET /data/{symbol}/historical` - Historical bars
- `GET /data/{symbol}/quote` - Real-time quote
- `GET /data/{symbol}/price` - Current price
- `GET /data/{symbol}/closes` - Close prices array

### 3. Strategy Engine Service (Port 8002)
**Responsibility**: Technical indicator calculation and signal generation

- RSI strategy
- MACD strategy
- Signal publishing

**Endpoints**:
- `POST /strategy/rsi/signal` - Calculate RSI signal
- `POST /strategy/macd/signal` - Calculate MACD signal
- `GET /strategy/rsi/calculate` - Raw RSI values
- `GET /strategy/macd/calculate` - Raw MACD values
- `GET /strategies` - List available strategies

### 4. Execution Service (Port 8003)
**Responsibility**: Order management and execution

- Pre-trade validation (calls Risk & Compliance)
- Order placement
- Trade event publishing

**Endpoints**:
- `POST /orders/buy` - Place buy order
- `POST /orders/sell` - Place sell order
- `GET /orders/{order_id}` - Order status
- `DELETE /orders/{order_id}` - Cancel order

### 5. Risk Management Service (Port 8004)
**Responsibility**: Position sizing and risk controls

- Order validation
- Position size calculation
- Profit target / stop loss monitoring

**Endpoints**:
- `POST /risk/validate-order` - Validate order
- `POST /risk/calculate-position` - Calculate position size
- `POST /risk/check-exit` - Check exit conditions
- `GET /risk/exposure` - Current exposure
- `GET /risk/config` - Risk configuration

### 6. Compliance Service (Port 8005)
**Responsibility**: PDT tracking and regulatory compliance

- Day trade counting
- PDT rule enforcement
- Trade recording

**Endpoints**:
- `GET /compliance/pdt-status` - PDT status
- `POST /compliance/can-trade` - Pre-trade check
- `POST /compliance/record-trade` - Record trade
- `GET /compliance/day-trades` - List day trades

### 7. Portfolio Service (Port 8006)
**Responsibility**: Position and P&L tracking

- Position management
- Transaction history
- P&L calculations

**Endpoints**:
- `GET /portfolio/positions` - All positions
- `GET /portfolio/positions/{symbol}` - Position by symbol
- `GET /portfolio/transactions` - Transaction history
- `GET /portfolio/pnl` - P&L summary
- `GET /portfolio/summary` - Full summary
- `POST /portfolio/update` - Update position

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Copy `.env.example` to `.env` and configure

### Start Services

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Health Checks

```bash
# Check all services
curl http://localhost:8000/health  # Gateway
curl http://localhost:8001/health  # Market Data
curl http://localhost:8002/health  # Strategy Engine
curl http://localhost:8003/health  # Execution
curl http://localhost:8004/health  # Risk Management
curl http://localhost:8005/health  # Compliance
curl http://localhost:8006/health  # Portfolio
```

## Event Flow

### Trade Execution Flow

1. **Market Data** → Publishes `price_update` event
2. **Strategy Engine** → Subscribes, calculates signal
3. **Strategy Engine** → Publishes `signal_generated` event
4. **Execution** → Validates with Risk Management
5. **Execution** → Checks Compliance (PDT)
6. **Execution** → Places order with Robinhood
7. **Execution** → Publishes `trade_completed` event
8. **Portfolio** → Updates positions
9. **Compliance** → Records day trade if applicable

## Configuration

### Environment Variables

```env
# Robinhood Credentials
ROBINHOOD_USERNAME=your_username
ROBINHOOD_PASSWORD=your_password

# Trading
SYMBOL=TQQQ
MAX_INVESTMENT=20.00
PROFIT_TARGET_PCT=1.0
STOP_LOSS_PCT=-0.5

# Strategy
RSI_PERIOD=14
RSI_OVERSOLD=30
RSI_OVERBOUGHT=70
MACD_FAST=12
MACD_SLOW=26
MACD_SIGNAL=9

# PDT
PDT_TRACKING_DAYS=5
MAX_DAY_TRADES=3
```

## Development

### Run Individual Service

```bash
cd services/strategy-engine
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8002
```

### Run Tests

```bash
pytest tests/
```

## Project Structure

```
├── docker-compose.yml
├── .env.example
├── shared/
│   ├── models/          # Pydantic data models
│   ├── messaging/       # Redis pub/sub utilities
│   └── utils/           # Config, logging
├── services/
│   ├── gateway/
│   ├── market-data/
│   ├── strategy-engine/
│   ├── execution/
│   ├── risk-management/
│   ├── compliance/
│   └── portfolio/
├── scripts/
│   └── init-db.sql      # Database initialization
├── tests/
└── legacy/              # Original monolithic bots
```

## Migration from Monolith

The original `RobinhoodBot.py` and `RobinhoodMACDBot.py` have been preserved in the `legacy/` directory. The microservices architecture provides:

- **Separation of concerns** - Each service has a single responsibility
- **Independent scaling** - Scale services based on load
- **Better testability** - Test services in isolation
- **Improved resilience** - Service failures are isolated
- **Easier maintenance** - Smaller, focused codebases
