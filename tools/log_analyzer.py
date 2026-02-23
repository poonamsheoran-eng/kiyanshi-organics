#!/usr/bin/env python3
"""
Log Analyzer for Kiyanshi Organics
Analyzes production logs and generates reports

Usage:
    python tools/log_analyzer.py logs.txt
"""

import re
from collections import Counter
import sys

def parse_log_line(line):
    """
    Parse a single log line and extract useful information
    
    Example input:
    "2024-02-16 10:30:15 - INFO - [abc123] - Request: GET /api/products"
    
    Returns:
    {
        'timestamp': '2024-02-16 10:30:15',
        'level': 'INFO',
        'message': 'Request: GET /api/products'
    }
    """
    # Pattern to match log format
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).+?(\w+).+?\[.+?\].+?- (.+)'
    
    match = re.search(pattern, line)
    if match:
        timestamp, level, message = match.groups()
        return {
            'timestamp': timestamp,
            'level': level,
            'message': message.strip()
        }
    return None


def analyze_logs(log_file):
    """
    Read log file and extract statistics
    
    Returns a dictionary with:
    - errors: list of error entries
    - slow_requests: list of slow requests (>1s)
    - endpoint_stats: counter of endpoint hits
    - status_codes: counter of HTTP status codes
    """
    
    errors = []
    slow_requests = []
    endpoint_stats = Counter()
    status_codes = Counter()
    
    print(f"📖 Reading log file: {log_file}")
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            print(f"📄 Found {len(lines)} log entries")
            
            for line in lines:
                parsed = parse_log_line(line)
                if not parsed:
                    continue
                
                message = parsed['message']
                
                # 1. Track errors
                if parsed['level'] == 'ERROR':
                    errors.append(parsed)
                
                # 2. Track endpoint usage
                if 'Request:' in message:
                    # Extract endpoint from "Request: GET /api/products"
                    parts = message.split()
                    if len(parts) >= 3:
                        endpoint = parts[2]
                        endpoint_stats[endpoint] += 1
                
                # 3. Track slow requests
                if 'Response:' in message and 'Time:' in message:
                    # Extract time from "Time: 1.234s"
                    time_match = re.search(r'Time: ([\d.]+)s', message)
                    if time_match:
                        time_taken = float(time_match.group(1))
                        if time_taken > 1.0:  # Slow = more than 1 second
                            endpoint_match = re.search(r'Response: \w+ (\S+)', message)
                            if endpoint_match:
                                slow_requests.append({
                                    'endpoint': endpoint_match.group(1),
                                    'time': time_taken,
                                    'timestamp': parsed['timestamp']
                                })
                
                # 4. Track HTTP status codes
                if 'Status:' in message:
                    status_match = re.search(r'Status: (\d+)', message)
                    if status_match:
                        status_codes[status_match.group(1)] += 1
        
        return {
            'errors': errors,
            'slow_requests': slow_requests,
            'endpoint_stats': endpoint_stats,
            'status_codes': status_codes
        }
    
    except FileNotFoundError:
        print(f"❌ Error: File '{log_file}' not found!")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        sys.exit(1)


def generate_report(stats):
    """
    Generate a human-readable report from statistics
    """
    
    print("\n" + "=" * 60)
    print("KIYANSHI ORGANICS - LOG ANALYSIS REPORT")
    print("=" * 60)
    print()
    
    # 1. Error Summary
    print("🔴 ERRORS:")
    if stats['errors']:
        print(f"  Found {len(stats['errors'])} errors")
        # Show last 5 errors
        for error in stats['errors'][-5:]:
            print(f"  [{error['timestamp']}] {error['message']}")
    else:
        print("  ✅ No errors found!")
    print()
    
    # 2. Slow Requests
    print("🐌 SLOW REQUESTS (>1s):")
    if stats['slow_requests']:
        print(f"  Found {len(stats['slow_requests'])} slow requests")
        # Show top 5 slowest
        sorted_slow = sorted(stats['slow_requests'], 
                           key=lambda x: x['time'], 
                           reverse=True)[:5]
        for req in sorted_slow:
            print(f"  {req['endpoint']}: {req['time']:.2f}s at {req['timestamp']}")
    else:
        print("  ✅ All requests fast!")
    print()
    
    # 3. Top Endpoints
    print("📊 TOP ENDPOINTS:")
    if stats['endpoint_stats']:
        for endpoint, count in stats['endpoint_stats'].most_common(10):
            print(f"  {endpoint}: {count} requests")
    else:
        print("  No endpoint data found")
    print()
    
    # 4. Status Codes
    print("📈 HTTP STATUS CODES:")
    if stats['status_codes']:
        for status, count in sorted(stats['status_codes'].items()):
            emoji = "✅" if status.startswith('2') else "⚠️" if status.startswith('4') else "❌"
            print(f"  {emoji} {status}: {count}")
    else:
        print("  No status code data found")
    print()
    
    # 5. Summary
    total_requests = sum(stats['status_codes'].values())
    success_requests = sum(count for status, count in stats['status_codes'].items() 
                          if status.startswith('2'))
    success_rate = (success_requests / total_requests * 100) if total_requests > 0 else 0
    
    print("📋 SUMMARY:")
    print(f"  Total Requests: {total_requests}")
    print(f"  Success Rate: {success_rate:.2f}%")
    print(f"  Total Errors: {len(stats['errors'])}")
    print(f"  Slow Requests: {len(stats['slow_requests'])}")
    print()


def main():
    """Main function"""
    
    if len(sys.argv) < 2:
        print("❌ Usage: python log_analyzer.py <logfile>")
        print("\nExample:")
        print("  python tools/log_analyzer.py logs/production.log")
        sys.exit(1)
    
    log_file = sys.argv[1]
    
    print("🔍 Kiyanshi Organics Log Analyzer")
    print("=" * 60)
    
    # Analyze logs
    stats = analyze_logs(log_file)
    
    # Generate report
    generate_report(stats)
    
    print("✅ Analysis complete!")


if __name__ == "__main__":
    main()
