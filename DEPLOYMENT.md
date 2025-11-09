# Deployment Guide - Running the MACD Bot Continuously

This guide shows you how to run the Robinhood MACD Trading Bot continuously without human intervention, so it monitors MACD 24/7 automatically.

## Table of Contents
1. [Quick Start - Background Process](#quick-start---background-process)
2. [Option 1: Systemd Service (Recommended for Linux)](#option-1-systemd-service-recommended-for-linux)
3. [Option 2: Docker Container](#option-2-docker-container)
4. [Option 3: Screen/Tmux Session](#option-3-screentmux-session)
5. [Option 4: Simple Background Script](#option-4-simple-background-script)
6. [Monitoring the Bot](#monitoring-the-bot)
7. [Auto-Restart on Crash](#auto-restart-on-crash)

---

## Quick Start - Background Process

The fastest way to run the bot in the background:

```bash
# Make the startup script executable
chmod +x start_bot.sh

# Run in background mode
./start_bot.sh background

# View logs
tail -f logs/nohup.out
```

---

## Option 1: Systemd Service (Recommended for Linux)

This is the **best option** for production deployment on Linux. The bot will:
- Start automatically on system boot
- Restart automatically if it crashes
- Run in the background with logging
- Be managed like any other system service

### Installation Steps

1. **Edit the bot configuration** with your credentials:
```bash
nano RobinhoodMACDBot.py
# Update CONFIG['username'] and CONFIG['password']
```

2. **Create logs directory**:
```bash
mkdir -p logs
```

3. **Install the systemd service**:
```bash
# Copy service file to systemd directory
sudo cp macd-bot.service /etc/systemd/system/

# Replace %i with your username in the service file
sudo sed -i "s/%i/$USER/g" /etc/systemd/system/macd-bot.service

# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable macd-bot.service

# Start the service now
sudo systemctl start macd-bot.service
```

### Managing the Service

```bash
# Check status
sudo systemctl status macd-bot.service

# View logs
sudo journalctl -u macd-bot.service -f

# View logs from today
sudo journalctl -u macd-bot.service --since today

# Stop the bot
sudo systemctl stop macd-bot.service

# Restart the bot
sudo systemctl restart macd-bot.service

# Disable auto-start on boot
sudo systemctl disable macd-bot.service
```

### Viewing Logs

Logs are saved to two locations:
1. **Application logs**: `~/RobinHood-RSI-Trading-Bot/logs/`
2. **System logs**: `sudo journalctl -u macd-bot.service`

```bash
# Follow application logs
tail -f ~/RobinHood-RSI-Trading-Bot/logs/macd_bot_*.log

# Follow system logs
sudo journalctl -u macd-bot.service -f
```

---

## Option 2: Docker Container

Run the bot in a Docker container for isolation and easy deployment.

### Prerequisites
- Docker installed: `curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh`
- Docker Compose installed (optional but recommended)

### Using Docker Compose (Easiest)

1. **Edit configuration**:
```bash
nano RobinhoodMACDBot.py
# Update CONFIG['username'] and CONFIG['password']
```

2. **Start the container**:
```bash
docker-compose up -d
```

3. **View logs**:
```bash
docker-compose logs -f
```

4. **Stop the container**:
```bash
docker-compose down
```

5. **Restart after code changes**:
```bash
docker-compose up -d --build
```

### Using Docker Only

```bash
# Build the image
docker build -t macd-bot .

# Run the container
docker run -d \
  --name macd-bot \
  --restart unless-stopped \
  -v $(pwd)/transactions.json:/app/transactions.json \
  -v $(pwd)/logs:/app/logs \
  macd-bot

# View logs
docker logs -f macd-bot

# Stop the container
docker stop macd-bot

# Remove the container
docker rm macd-bot
```

### Docker Benefits
- **Isolation**: Bot runs in its own environment
- **Portability**: Run on any system with Docker
- **Easy Updates**: Rebuild and restart with one command
- **Resource Limits**: Can set CPU/memory limits

---

## Option 3: Screen/Tmux Session

Use `screen` or `tmux` to run the bot in a detachable terminal session.

### Using Screen

```bash
# Install screen if not available
sudo apt-get install screen

# Create a new screen session
screen -S macd-bot

# Run the bot
python3 RobinhoodMACDBot.py

# Detach from screen: Press Ctrl+A, then D

# Reattach to screen
screen -r macd-bot

# List all screen sessions
screen -ls

# Kill the screen session
screen -S macd-bot -X quit
```

### Using Tmux

```bash
# Install tmux if not available
sudo apt-get install tmux

# Create a new tmux session
tmux new -s macd-bot

# Run the bot
python3 RobinhoodMACDBot.py

# Detach from tmux: Press Ctrl+B, then D

# Reattach to tmux
tmux attach -t macd-bot

# List all tmux sessions
tmux ls

# Kill the tmux session
tmux kill-session -t macd-bot
```

### Benefits
- Simple and lightweight
- Easy to attach and see real-time output
- No configuration needed
- Great for development/testing

---

## Option 4: Simple Background Script

Use the included startup script with auto-restart functionality.

```bash
# Make executable
chmod +x start_bot.sh

# Run in foreground with auto-restart
./start_bot.sh

# Run in background
./start_bot.sh background

# Or use nohup directly
nohup python3 RobinhoodMACDBot.py > logs/bot.log 2>&1 &

# Save the process ID
echo $! > bot.pid

# Stop the bot
kill $(cat bot.pid)
```

---

## Monitoring the Bot

### Check if Bot is Running

```bash
# Using systemd
sudo systemctl status macd-bot.service

# Using Docker
docker ps | grep macd-bot

# Using screen
screen -ls | grep macd-bot

# Using process list
ps aux | grep RobinhoodMACDBot.py
```

### View Real-Time Logs

```bash
# Application logs
tail -f logs/macd_bot_$(date +%Y%m%d).log

# Or all log files
tail -f logs/*.log

# With color highlighting (requires ccze)
tail -f logs/*.log | ccze -A
```

### View Transaction History

```bash
# Pretty print transaction JSON
cat transactions.json | python3 -m json.tool

# Count total transactions
cat transactions.json | python3 -c "import json,sys; print(len(json.load(sys.stdin)['transactions']))"

# View recent transactions
tail -20 logs/macd_bot_*.log | grep "ORDER PLACED"
```

### Set Up Alerts (Optional)

Monitor for critical events and get notified:

```bash
# Monitor for errors
tail -f logs/*.log | grep -i "error" | while read line; do
    echo "ERROR DETECTED: $line"
    # Add email/SMS notification here
done

# Monitor for trades
tail -f logs/*.log | grep "ORDER PLACED" | while read line; do
    echo "TRADE EXECUTED: $line"
    # Add notification here
done
```

---

## Auto-Restart on Crash

All deployment options include auto-restart functionality:

### Systemd
- **Restart Policy**: Defined in `macd-bot.service`
- Automatically restarts after 10 seconds if crashed
- Limited to 5 restart attempts per 200 seconds

### Docker
- **Restart Policy**: `unless-stopped` in docker-compose.yml
- Automatically restarts unless manually stopped

### Startup Script
- **While Loop**: Automatically restarts after 10 seconds
- Logs crash events

---

## Troubleshooting

### Bot Not Starting

1. **Check credentials**:
```bash
grep -E "username|password" RobinhoodMACDBot.py
```

2. **Check dependencies**:
```bash
pip3 install -r requirements.txt
```

3. **Check Python version** (requires 3.7+):
```bash
python3 --version
```

4. **Check logs for errors**:
```bash
tail -50 logs/macd_bot_*.log
```

### Bot Stops Running

1. **Check system logs**:
```bash
sudo journalctl -u macd-bot.service --since "1 hour ago"
```

2. **Check for crashes**:
```bash
grep -i "traceback\|error\|exception" logs/*.log
```

3. **Verify network connectivity**:
```bash
ping -c 4 api.robinhood.com
```

### 2FA Issues

If running in background, 2FA prompts won't work. Options:
1. Use Robinhood's "trusted device" feature
2. Consider using API tokens (if available)
3. Start in foreground first to complete 2FA, then run in background

---

## Best Practices

1. **Test First**: Run in foreground first to ensure everything works
2. **Monitor Initially**: Watch logs for the first few hours/days
3. **Set Alerts**: Configure notifications for trades and errors
4. **Regular Checks**: Review transaction logs daily
5. **Keep Updated**: Regularly update dependencies
6. **Backup Data**: Keep copies of `transactions.json`
7. **Resource Monitoring**: Ensure system has adequate resources

---

## Security Considerations

1. **Credentials**: Never commit credentials to git
2. **File Permissions**: Restrict access to bot files
```bash
chmod 600 RobinhoodMACDBot.py
chmod 700 logs/
```
3. **Log Rotation**: Implement log rotation to prevent disk fill
4. **Firewall**: Ensure only necessary ports are open
5. **Updates**: Keep system and dependencies updated

---

## Resource Usage

Typical resource usage:
- **CPU**: < 1% (mostly idle)
- **RAM**: ~50-100 MB
- **Disk**: ~1 MB per day (logs)
- **Network**: Minimal (API calls every 5 minutes)

---

## Recommended Setup

For most users, we recommend:

1. **Development/Testing**: Screen or Tmux
2. **Production (Linux)**: Systemd service
3. **Production (Cross-platform)**: Docker
4. **Quick Deploy**: Background script

Choose based on your comfort level and infrastructure!
