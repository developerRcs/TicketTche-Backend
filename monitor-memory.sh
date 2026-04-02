#!/bin/bash

# =============================================================================
# Memory Monitoring Script for Tickettche
# Monitors memory usage and sends alerts when thresholds are exceeded
# =============================================================================

# Configuration
MEMORY_WARNING_THRESHOLD=80  # Warn at 80%
MEMORY_CRITICAL_THRESHOLD=90  # Critical at 90%
LOG_FILE="/var/log/tickettche/memory-monitor.log"
ALERT_EMAIL="admin@tickettche.com"

# Colors for terminal output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Create log directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Function to get memory usage percentage
get_memory_usage() {
    free | grep Mem | awk '{printf "%.0f", ($3/$2) * 100.0}'
}

# Function to log with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to get top memory consumers
get_top_processes() {
    ps aux --sort=-%mem | head -n 11 | tail -n 10
}

# Function to send alert
send_alert() {
    local severity=$1
    local usage=$2
    local message="[$severity] Memory usage at ${usage}% on $(hostname)"

    # Log to file
    log_message "$message"

    # Send email (if mail is configured)
    if command -v mail &> /dev/null; then
        echo -e "$message\n\nTop memory consumers:\n$(get_top_processes)" | \
            mail -s "Tickettche Memory Alert - $severity" "$ALERT_EMAIL"
    fi

    # Log top processes
    log_message "Top memory consumers:"
    get_top_processes >> "$LOG_FILE"
}

# Function to check individual services
check_service_memory() {
    local service_name=$1
    local pid

    # Try to find PID
    if systemctl is-active --quiet "$service_name"; then
        pid=$(systemctl show -p MainPID "$service_name" | cut -d= -f2)
        if [ "$pid" != "0" ]; then
            local mem_usage=$(ps -p "$pid" -o %mem --no-headers | tr -d ' ')
            log_message "$service_name (PID $pid): ${mem_usage}% memory"
        fi
    fi
}

# Main monitoring logic
main() {
    MEMORY_USAGE=$(get_memory_usage)

    log_message "=== Memory Check ==="
    log_message "Total memory usage: ${MEMORY_USAGE}%"

    # Check individual services
    check_service_memory "tickettche-backend"
    check_service_memory "postgresql"
    check_service_memory "redis"

    # Check thresholds
    if [ "$MEMORY_USAGE" -ge "$MEMORY_CRITICAL_THRESHOLD" ]; then
        echo -e "${RED}CRITICAL: Memory at ${MEMORY_USAGE}%${NC}"
        send_alert "CRITICAL" "$MEMORY_USAGE"

        # Auto-remediation: Restart services if critically high
        log_message "Auto-remediation: Restarting services due to critical memory usage"
        systemctl restart tickettche-backend

    elif [ "$MEMORY_USAGE" -ge "$MEMORY_WARNING_THRESHOLD" ]; then
        echo -e "${YELLOW}WARNING: Memory at ${MEMORY_USAGE}%${NC}"
        send_alert "WARNING" "$MEMORY_USAGE"

    else
        echo -e "${GREEN}OK: Memory at ${MEMORY_USAGE}%${NC}"
    fi

    # Additional checks

    # Check for swap usage (should be zero on production)
    SWAP_USAGE=$(free | grep Swap | awk '{if ($2 > 0) printf "%.0f", ($3/$2) * 100.0; else print "0"}')
    if [ "$SWAP_USAGE" != "0" ] && [ "$SWAP_USAGE" -gt "0" ]; then
        log_message "WARNING: Swap in use (${SWAP_USAGE}%) - this degrades performance!"
    fi

    # Check for OOM killer activity
    if dmesg | tail -n 100 | grep -i "killed process" > /dev/null; then
        log_message "CRITICAL: OOM Killer has been active!"
        dmesg | grep -i "killed process" | tail -n 5 >> "$LOG_FILE"
    fi

    # Detailed memory breakdown
    log_message "Memory breakdown:"
    free -h | tee -a "$LOG_FILE"

    log_message "=== End Check ===\n"
}

# Run main function
main

# Exit with status based on memory usage
MEMORY_USAGE=$(get_memory_usage)
if [ "$MEMORY_USAGE" -ge "$MEMORY_CRITICAL_THRESHOLD" ]; then
    exit 2  # Critical
elif [ "$MEMORY_USAGE" -ge "$MEMORY_WARNING_THRESHOLD" ]; then
    exit 1  # Warning
else
    exit 0  # OK
fi
