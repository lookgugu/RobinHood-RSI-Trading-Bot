#!/usr/bin/env python3
"""
Log Management Utility for Robinhood MACD Trading Bot

This utility helps manage, analyze, and clean up log files.
"""

import os
import sys
import glob
import gzip
import shutil
import time
from datetime import datetime, timedelta
import argparse

LOG_DIR = 'logs'

def get_log_files(include_compressed=True):
    """Get all log files in the log directory"""
    patterns = [
        os.path.join(LOG_DIR, 'macd_bot.log*'),
        os.path.join(LOG_DIR, 'macd_bot_*.log*'),
    ]

    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))

    if not include_compressed:
        files = [f for f in files if not f.endswith('.gz')]

    return sorted(files)

def get_file_size(file_path):
    """Get human-readable file size"""
    size_bytes = os.path.getsize(file_path)

    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0

    return f"{size_bytes:.2f} TB"

def get_file_age_days(file_path):
    """Get file age in days"""
    file_mtime = os.path.getmtime(file_path)
    age_seconds = time.time() - file_mtime
    return int(age_seconds / (24 * 60 * 60))

def list_logs(args):
    """List all log files with details"""
    files = get_log_files()

    if not files:
        print("No log files found.")
        return

    print(f"\n{'Filename':<40} {'Size':<12} {'Age (days)':<12} {'Compressed'}")
    print("=" * 80)

    total_size = 0
    for file_path in files:
        filename = os.path.basename(file_path)
        size = os.path.getsize(file_path)
        total_size += size
        size_str = get_file_size(file_path)
        age = get_file_age_days(file_path)
        compressed = "Yes" if file_path.endswith('.gz') else "No"

        print(f"{filename:<40} {size_str:<12} {age:<12} {compressed}")

    print("=" * 80)
    print(f"Total: {len(files)} files, {get_file_size(sum(os.path.getsize(f) for f in files))}")
    print()

def compress_logs(args):
    """Compress uncompressed log files"""
    files = get_log_files(include_compressed=False)

    # Filter out the current log file
    files = [f for f in files if not f.endswith('macd_bot.log')]

    if not files:
        print("No uncompressed log files to compress.")
        return

    print(f"Found {len(files)} uncompressed log files.")

    if not args.force:
        response = input("Compress these files? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return

    compressed_count = 0
    for file_path in files:
        try:
            # Compress the file
            with open(file_path, 'rb') as f_in:
                with gzip.open(f"{file_path}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Remove the original
            os.remove(file_path)
            compressed_count += 1
            print(f"Compressed: {os.path.basename(file_path)}")

        except Exception as e:
            print(f"Error compressing {file_path}: {e}")

    print(f"\nCompressed {compressed_count} files.")

def cleanup_logs(args):
    """Delete log files older than specified days"""
    retention_days = args.days

    if retention_days <= 0:
        print("Error: Retention days must be positive.")
        return

    files = get_log_files()
    cutoff_time = time.time() - (retention_days * 24 * 60 * 60)

    old_files = []
    for file_path in files:
        # Skip the current log file
        if file_path.endswith('macd_bot.log'):
            continue

        file_mtime = os.path.getmtime(file_path)
        if file_mtime < cutoff_time:
            old_files.append(file_path)

    if not old_files:
        print(f"No log files older than {retention_days} days found.")
        return

    print(f"\nFound {len(old_files)} log files older than {retention_days} days:")
    for file_path in old_files:
        age = get_file_age_days(file_path)
        size = get_file_size(file_path)
        print(f"  {os.path.basename(file_path):<40} {size:<12} {age} days")

    if not args.force:
        response = input(f"\nDelete these {len(old_files)} files? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            return

    deleted_count = 0
    for file_path in old_files:
        try:
            os.remove(file_path)
            deleted_count += 1
            print(f"Deleted: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")

    print(f"\nDeleted {deleted_count} files.")

def view_log(args):
    """View log file contents"""
    log_file = args.file

    if not os.path.exists(log_file):
        # Try to find it in logs directory
        log_file = os.path.join(LOG_DIR, log_file)

    if not os.path.exists(log_file):
        print(f"Error: Log file not found: {args.file}")
        return

    # Check if compressed
    if log_file.endswith('.gz'):
        with gzip.open(log_file, 'rt') as f:
            content = f.read()
    else:
        with open(log_file, 'r') as f:
            content = f.read()

    # Apply filters
    lines = content.split('\n')

    if args.filter:
        lines = [line for line in lines if args.filter.lower() in line.lower()]

    if args.tail:
        lines = lines[-args.tail:]

    for line in lines:
        print(line)

def analyze_logs(args):
    """Analyze log files for statistics"""
    files = get_log_files()

    if not files:
        print("No log files found.")
        return

    print("\nLog Analysis")
    print("=" * 80)

    total_size = sum(os.path.getsize(f) for f in files)
    compressed_files = [f for f in files if f.endswith('.gz')]
    uncompressed_files = [f for f in files if not f.endswith('.gz')]

    print(f"Total log files: {len(files)}")
    print(f"  Compressed: {len(compressed_files)}")
    print(f"  Uncompressed: {len(uncompressed_files)}")
    print(f"Total size: {get_file_size(sum(os.path.getsize(f) for f in files))}")

    if files:
        oldest_file = min(files, key=os.path.getmtime)
        newest_file = max(files, key=os.path.getmtime)
        print(f"Oldest log: {os.path.basename(oldest_file)} ({get_file_age_days(oldest_file)} days old)")
        print(f"Newest log: {os.path.basename(newest_file)} ({get_file_age_days(newest_file)} days old)")

    # Count specific events in logs
    if args.detailed:
        print("\nSearching for events in logs...")
        trades = 0
        errors = 0
        warnings = 0

        for file_path in files:
            try:
                if file_path.endswith('.gz'):
                    with gzip.open(file_path, 'rt') as f:
                        content = f.read()
                else:
                    with open(file_path, 'r') as f:
                        content = f.read()

                trades += content.count('ORDER PLACED')
                errors += content.count('ERROR')
                warnings += content.count('WARNING')
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

        print(f"\nTotal trades logged: {trades}")
        print(f"Total errors: {errors}")
        print(f"Total warnings: {warnings}")

    print()

def main():
    parser = argparse.ArgumentParser(
        description='Manage log files for Robinhood MACD Trading Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                       # List all log files
  %(prog)s compress                   # Compress old log files
  %(prog)s cleanup --days 30          # Delete logs older than 30 days
  %(prog)s view macd_bot.log          # View current log
  %(prog)s view macd_bot.log.20250101.gz --tail 100  # View last 100 lines
  %(prog)s analyze --detailed         # Analyze logs with event counts
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # List command
    list_parser = subparsers.add_parser('list', help='List all log files')

    # Compress command
    compress_parser = subparsers.add_parser('compress', help='Compress uncompressed log files')
    compress_parser.add_argument('-f', '--force', action='store_true', help='Skip confirmation')

    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Delete old log files')
    cleanup_parser.add_argument('-d', '--days', type=int, default=90,
                                help='Delete logs older than N days (default: 90)')
    cleanup_parser.add_argument('-f', '--force', action='store_true', help='Skip confirmation')

    # View command
    view_parser = subparsers.add_parser('view', help='View log file contents')
    view_parser.add_argument('file', help='Log file to view')
    view_parser.add_argument('-t', '--tail', type=int, help='Show last N lines')
    view_parser.add_argument('-f', '--filter', help='Filter lines containing text')

    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze log files')
    analyze_parser.add_argument('-d', '--detailed', action='store_true',
                                help='Include detailed event counts (slower)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Ensure log directory exists
    if not os.path.exists(LOG_DIR):
        print(f"Error: Log directory '{LOG_DIR}' not found.")
        return

    # Execute command
    if args.command == 'list':
        list_logs(args)
    elif args.command == 'compress':
        compress_logs(args)
    elif args.command == 'cleanup':
        cleanup_logs(args)
    elif args.command == 'view':
        view_log(args)
    elif args.command == 'analyze':
        analyze_logs(args)

if __name__ == '__main__':
    main()
