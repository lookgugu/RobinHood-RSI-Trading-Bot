#!/bin/bash
# Startup script for Robinhood MACD Trading Bot
# This script ensures the bot runs continuously in the background

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to run the bot
run_bot() {
    echo "Starting Robinhood MACD Trading Bot..."
    echo "Logs will be saved to logs/ directory"
    echo "Press Ctrl+C to stop the bot"

    # Run with auto-restart on crash
    while true; do
        python3 RobinhoodMACDBot.py
        EXIT_CODE=$?

        if [ $EXIT_CODE -eq 0 ]; then
            echo "Bot exited cleanly. Stopping."
            break
        else
            echo "Bot crashed with exit code $EXIT_CODE. Restarting in 10 seconds..."
            sleep 10
        fi
    done
}

# Check if running in background mode
if [ "$1" == "background" ] || [ "$1" == "daemon" ]; then
    echo "Starting bot in background mode..."
    nohup bash -c "$(declare -f run_bot); run_bot" > logs/nohup.out 2>&1 &
    echo "Bot started in background with PID: $!"
    echo "To view logs: tail -f logs/nohup.out"
    echo "To stop: kill $!"
else
    # Run in foreground
    run_bot
fi
