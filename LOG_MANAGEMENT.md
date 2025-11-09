# Log Management Guide

Complete guide for managing logs in the Robinhood MACD Trading Bot to ensure you have sufficient information without worrying about consuming all disk space.

## Table of Contents
1. [Overview](#overview)
2. [Log Rotation](#log-rotation)
3. [Automatic Compression](#automatic-compression)
4. [Automatic Cleanup](#automatic-cleanup)
5. [Manual Log Management](#manual-log-management)
6. [Configuration Options](#configuration-options)
7. [Disk Space Estimation](#disk-space-estimation)
8. [Best Practices](#best-practices)

---

## Overview

The bot includes a comprehensive log management system that:
- **Automatically rotates logs** (daily or by size)
- **Compresses old logs** with gzip (saves ~90% space)
- **Deletes logs** older than retention period
- **Prevents disk fill** with configurable limits
- **Provides tools** for log analysis and management

### Log File Naming

- **Current log**: `logs/macd_bot.log`
- **Rotated logs**: `logs/macd_bot.log.20250109` (date-based)
- **Compressed logs**: `logs/macd_bot.log.20250109.gz`

---

## Log Rotation

### Time-Based Rotation (Default)

Logs rotate **daily at midnight**:

```python
CONFIG = {
    'log_rotation_type': 'time',  # Daily rotation
    'log_backup_count': 30,        # Keep 30 days
}
```

**How it works:**
- At midnight, current log is renamed with date suffix
- New log file is created
- Keeps the last 30 rotated files
- Automatically deletes older backups

**Disk space**: ~30 days of logs (compressed)

### Size-Based Rotation

Logs rotate when they reach **10 MB** (default):

```python
CONFIG = {
    'log_rotation_type': 'size',           # Size-based rotation
    'log_max_bytes': 10 * 1024 * 1024,    # 10 MB per file
    'log_backup_count': 30,                # Keep 30 files
}
```

**How it works:**
- When log reaches 10 MB, it rotates
- Creates numbered backups (`.1`, `.2`, etc.)
- Keeps 30 backup files
- Automatically deletes oldest backup

**Disk space**: ~300 MB maximum (30 × 10 MB)

---

## Automatic Compression

Old log files are **automatically compressed with gzip** to save ~90% disk space.

### When Compression Happens

1. **On bot startup**: Compresses any uncompressed old logs
2. **After rotation**: New backups are compressed
3. **Manual**: Using `manage_logs.py compress`

### Configuration

```python
CONFIG = {
    'log_compress_archives': True,  # Enable compression (default)
}
```

### Compression Ratio

| File Type | Uncompressed | Compressed | Savings |
|-----------|--------------|------------|---------|
| Text logs | 10 MB | ~1 MB | 90% |
| Daily log | ~2 MB | ~200 KB | 90% |

**Example**: 30 days of logs
- Uncompressed: ~60 MB
- Compressed: ~6 MB
- **Savings: 54 MB (90%)**

---

## Automatic Cleanup

Old logs are **automatically deleted** based on retention period.

### Configuration

```python
CONFIG = {
    'log_retention_days': 90,  # Delete logs older than 90 days
}
```

### When Cleanup Happens

1. **On bot startup**: Checks and deletes old logs
2. **Manual**: Using `manage_logs.py cleanup`

### Examples

| Retention Days | Disk Space (compressed) | Use Case |
|----------------|-------------------------|----------|
| 7 | ~1 MB | Testing/development |
| 30 | ~6 MB | Normal operation |
| 90 | ~18 MB | Long-term analysis |
| 365 | ~73 MB | Full year history |

**Recommendation**: 90 days provides good balance between history and disk space

---

## Manual Log Management

The `manage_logs.py` utility provides manual control over logs.

### List All Logs

```bash
./manage_logs.py list
```

**Output:**
```
Filename                                 Size         Age (days)   Compressed
================================================================================
macd_bot.log                            432.15 KB    0            No
macd_bot.log.20250108.gz                89.23 KB     1            Yes
macd_bot.log.20250107.gz                91.45 KB     2            Yes
macd_bot.log.20250106.gz                88.76 KB     3            Yes
================================================================================
Total: 4 files, 701.59 KB
```

### Compress Uncompressed Logs

```bash
# Interactive (asks for confirmation)
./manage_logs.py compress

# Force (no confirmation)
./manage_logs.py compress --force
```

### Cleanup Old Logs

```bash
# Delete logs older than 90 days (interactive)
./manage_logs.py cleanup --days 90

# Delete logs older than 30 days (force)
./manage_logs.py cleanup --days 30 --force
```

### View Log Files

```bash
# View current log
./manage_logs.py view macd_bot.log

# View compressed log (automatically decompresses)
./manage_logs.py view macd_bot.log.20250108.gz

# View last 100 lines
./manage_logs.py view macd_bot.log --tail 100

# Filter for specific content
./manage_logs.py view macd_bot.log --filter "ORDER PLACED"
./manage_logs.py view macd_bot.log --filter "error"
```

### Analyze Logs

```bash
# Basic analysis
./manage_logs.py analyze

# Detailed analysis (counts trades, errors, warnings)
./manage_logs.py analyze --detailed
```

**Example output:**
```
Log Analysis
================================================================================
Total log files: 31
  Compressed: 30
  Uncompressed: 1
Total size: 7.23 MB
Oldest log: macd_bot.log.20241210.gz (30 days old)
Newest log: macd_bot.log (0 days old)

Total trades logged: 47
Total errors: 2
Total warnings: 5
```

---

## Configuration Options

### Complete Logging Configuration

```python
CONFIG = {
    # Basic Logging
    'log_to_file': True,              # Enable file logging
    'log_directory': 'logs',          # Log directory path

    # Rotation
    'log_rotation_type': 'time',      # 'time' or 'size'
    'log_max_bytes': 10485760,        # 10 MB (for size rotation)
    'log_backup_count': 30,           # Number of backups to keep

    # Compression & Cleanup
    'log_compress_archives': True,    # Compress old logs with gzip
    'log_retention_days': 90,         # Delete logs older than N days
}
```

### Recommended Configurations

#### Minimal Disk Usage (Development)
```python
'log_rotation_type': 'size',
'log_max_bytes': 5 * 1024 * 1024,    # 5 MB
'log_backup_count': 5,                # 5 files = 25 MB max
'log_compress_archives': True,
'log_retention_days': 7,              # 1 week
```
**Disk space**: ~3-5 MB

#### Balanced (Production)
```python
'log_rotation_type': 'time',          # Daily
'log_backup_count': 30,               # 30 days
'log_compress_archives': True,
'log_retention_days': 90,             # 3 months
```
**Disk space**: ~6-18 MB

#### Maximum History
```python
'log_rotation_type': 'time',          # Daily
'log_backup_count': 365,              # 1 year
'log_compress_archives': True,
'log_retention_days': 730,            # 2 years
```
**Disk space**: ~150-200 MB

---

## Disk Space Estimation

### Calculation

Daily log size depends on activity:
- **Low activity**: ~500 KB/day (checking every 5 min, no trades)
- **Normal activity**: ~2 MB/day (few trades)
- **High activity**: ~5 MB/day (many trades, errors)

**Formula:**
```
Uncompressed = Daily_Size × Retention_Days
Compressed = Uncompressed × 0.1  (90% compression)
```

### Examples

| Activity | Daily Size | 30 Days (Compressed) | 90 Days (Compressed) | 365 Days (Compressed) |
|----------|-----------|----------------------|----------------------|-----------------------|
| Low | 500 KB | ~1.5 MB | ~4.5 MB | ~18 MB |
| Normal | 2 MB | ~6 MB | ~18 MB | ~73 MB |
| High | 5 MB | ~15 MB | ~45 MB | ~183 MB |

**Worst case** (365 days, high activity): ~200 MB

---

## Best Practices

### 1. Choose Appropriate Retention

```python
# Development: Short retention
'log_retention_days': 7,

# Production: Medium retention
'log_retention_days': 90,

# Compliance/Audit: Long retention
'log_retention_days': 365,
```

### 2. Enable Compression

Always keep compression enabled:
```python
'log_compress_archives': True,  # Saves 90% disk space
```

### 3. Regular Monitoring

Set up a weekly cron job to check logs:
```bash
# Add to crontab (runs every Sunday at 2 AM)
0 2 * * 0 cd /path/to/bot && ./manage_logs.py analyze --detailed
```

### 4. Monitor Disk Space

Check available disk space:
```bash
# Check disk usage
df -h

# Check log directory size
du -sh logs/

# Check total log size by type
du -sh logs/*.log        # Uncompressed
du -sh logs/*.log.*.gz   # Compressed
```

### 5. Archive Important Logs

Before cleanup, archive important periods:
```bash
# Create archive of specific month
tar -czf logs_2025-01.tar.gz logs/macd_bot.log.202501*.gz

# Move to backup location
mv logs_2025-01.tar.gz /backup/trading-bot/
```

### 6. Set Disk Space Alerts

Create a monitoring script:
```bash
#!/bin/bash
# alert_disk_space.sh

THRESHOLD=90  # Alert at 90% full
USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')

if [ $USAGE -gt $THRESHOLD ]; then
    echo "WARNING: Disk usage at ${USAGE}%"
    # Add email/SMS notification here
fi
```

### 7. Rotate by Size for Limited Disks

If disk space is very limited:
```python
'log_rotation_type': 'size',
'log_max_bytes': 5 * 1024 * 1024,  # 5 MB
'log_backup_count': 10,             # Max 50 MB total
```

---

## Viewing Compressed Logs

### Using manage_logs.py (Easiest)

```bash
./manage_logs.py view logs/macd_bot.log.20250108.gz
```

### Using zcat/zless

```bash
# View entire file
zcat logs/macd_bot.log.20250108.gz

# Page through file
zless logs/macd_bot.log.20250108.gz

# Search in compressed file
zgrep "ORDER PLACED" logs/macd_bot.log.20250108.gz

# Last 100 lines
zcat logs/macd_bot.log.20250108.gz | tail -100
```

### Decompress Permanently

```bash
# Decompress (keeps original)
gunzip -k logs/macd_bot.log.20250108.gz

# Decompress (removes .gz)
gunzip logs/macd_bot.log.20250108.gz
```

---

## Troubleshooting

### Logs Growing Too Fast

**Problem**: Log files are larger than expected

**Solutions:**
1. Reduce `check_interval` if checking too frequently
2. Decrease `log_backup_count` to keep fewer files
3. Lower `log_retention_days`
4. Switch to size-based rotation with smaller limits

```python
# More aggressive rotation
'log_rotation_type': 'size',
'log_max_bytes': 5 * 1024 * 1024,  # 5 MB instead of 10 MB
'log_backup_count': 15,             # 15 instead of 30
```

### Disk Space Running Out

**Immediate actions:**
```bash
# 1. Check current usage
./manage_logs.py analyze

# 2. Compress uncompressed logs
./manage_logs.py compress --force

# 3. Delete logs older than 30 days
./manage_logs.py cleanup --days 30 --force

# 4. Check disk space freed
df -h
```

**Long-term solutions:**
1. Reduce retention period
2. Archive old logs to external storage
3. Use size-based rotation with smaller limits

### Cannot Delete Log Files

**Problem**: Permission denied when deleting logs

**Solution:**
```bash
# Fix permissions
sudo chown -R $USER:$USER logs/
chmod -R u+w logs/
```

### Compression Not Working

**Check:**
1. `log_compress_archives` is `True`
2. `gzip` is installed: `which gzip`
3. Write permissions: `ls -la logs/`

---

## Automated Maintenance

### Setup Cron Jobs

```bash
# Edit crontab
crontab -e

# Add these lines:

# Compress logs daily at 1 AM
0 1 * * * cd /path/to/bot && ./manage_logs.py compress --force >> /tmp/log_compress.log 2>&1

# Cleanup old logs weekly (Sunday at 2 AM)
0 2 * * 0 cd /path/to/bot && ./manage_logs.py cleanup --days 90 --force >> /tmp/log_cleanup.log 2>&1

# Analyze logs monthly (1st of month at 3 AM)
0 3 1 * * cd /path/to/bot && ./manage_logs.py analyze --detailed > /tmp/log_analysis.txt
```

### Systemd Timer (Alternative to Cron)

Create `/etc/systemd/system/macd-bot-cleanup.service`:
```ini
[Unit]
Description=MACD Bot Log Cleanup

[Service]
Type=oneshot
WorkingDirectory=/home/user/RobinHood-RSI-Trading-Bot
ExecStart=/usr/bin/python3 manage_logs.py cleanup --days 90 --force
```

Create `/etc/systemd/system/macd-bot-cleanup.timer`:
```ini
[Unit]
Description=Run MACD Bot Log Cleanup Weekly

[Timer]
OnCalendar=weekly
Persistent=true

[Install]
WantedBy=timers.target
```

Enable:
```bash
sudo systemctl enable macd-bot-cleanup.timer
sudo systemctl start macd-bot-cleanup.timer
```

---

## Summary

### Default Behavior (Out of the Box)

✅ **Daily log rotation** at midnight
✅ **30 days** of rotated logs kept
✅ **Automatic gzip compression** (~90% space savings)
✅ **90-day retention** (auto-delete older logs)
✅ **~6-18 MB disk space** for normal operation

### What You Control

| Setting | Controls | Impact |
|---------|----------|--------|
| `log_rotation_type` | When logs rotate | time = daily, size = when full |
| `log_backup_count` | Number of backups | More = more history, more space |
| `log_retention_days` | When to delete | Lower = less disk space |
| `log_compress_archives` | Compression | True = save 90% space |
| `log_max_bytes` | Rotation size | Smaller = more frequent rotation |

### Quick Reference

```bash
# View all logs
./manage_logs.py list

# Analyze disk usage
./manage_logs.py analyze

# Free up space immediately
./manage_logs.py cleanup --days 30 --force

# View recent activity
./manage_logs.py view macd_bot.log --tail 100

# Search for trades
./manage_logs.py view macd_bot.log --filter "ORDER PLACED"
```

---

**You now have complete control over your logs without worrying about disk space!** 🎉
