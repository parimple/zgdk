#!/bin/bash
# Setup cron job for automatic database backups

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup_database.sh"
CRON_LOG="/home/ubuntu/logs/zgdk_backup.log"

# Create log directory
mkdir -p "$(dirname "${CRON_LOG}")"

# Function to add cron job
add_cron_job() {
    local schedule="$1"
    local job="$2"
    
    # Check if job already exists
    if crontab -l 2>/dev/null | grep -q "${job}"; then
        echo "Cron job already exists"
        return 0
    fi
    
    # Add new job
    (crontab -l 2>/dev/null; echo "${schedule} ${job}") | crontab -
    echo "Cron job added: ${schedule} ${job}"
}

echo "Setting up automatic database backups..."
echo ""
echo "Available schedules:"
echo "1) Every 6 hours"
echo "2) Daily at 3 AM"
echo "3) Daily at custom time"
echo "4) Custom cron expression"
echo ""
read -p "Select schedule (1-4): " choice

case $choice in
    1)
        SCHEDULE="0 */6 * * *"
        echo "Selected: Every 6 hours"
        ;;
    2)
        SCHEDULE="0 3 * * *"
        echo "Selected: Daily at 3 AM"
        ;;
    3)
        read -p "Enter hour (0-23): " hour
        read -p "Enter minute (0-59): " minute
        SCHEDULE="${minute} ${hour} * * *"
        echo "Selected: Daily at ${hour}:${minute}"
        ;;
    4)
        read -p "Enter cron expression: " SCHEDULE
        echo "Selected: ${SCHEDULE}"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

# Create cron job command
CRON_JOB="${BACKUP_SCRIPT} >> ${CRON_LOG} 2>&1"

# Add to crontab
add_cron_job "${SCHEDULE}" "${CRON_JOB}"

echo ""
echo "Backup schedule configured!"
echo "View current cron jobs: crontab -l"
echo "View backup logs: tail -f ${CRON_LOG}"
echo "Remove backup job: crontab -e (and delete the line)"
echo ""
echo "Testing backup script..."
${BACKUP_SCRIPT}