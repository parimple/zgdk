#!/bin/bash
# Database restore script for zgdk bot

# Configuration
BACKUP_DIR="/home/ubuntu/backups/zgdk"
CONTAINER_NAME="zgdk-db-1"
DB_NAME="postgres"
DB_USER="postgres"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Check if backup file is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Available backups:"
    ls -lh "${BACKUP_DIR}"/zgdk_backup_*.sql.gz 2>/dev/null | awk '{print $9, $5}'
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    # Try in backup directory
    if [ ! -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
        log "ERROR: Backup file not found: ${BACKUP_FILE}"
        exit 1
    fi
    BACKUP_FILE="${BACKUP_DIR}/${BACKUP_FILE}"
fi

log "Starting database restore from: ${BACKUP_FILE}"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log "ERROR: Database container ${CONTAINER_NAME} is not running!"
    exit 1
fi

# Warning
echo ""
echo "WARNING: This will replace ALL data in the database!"
echo "Container: ${CONTAINER_NAME}"
echo "Database: ${DB_NAME}"
echo "Backup: ${BACKUP_FILE}"
echo ""
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    log "Restore cancelled by user"
    exit 0
fi

# Create temporary uncompressed file if needed
TEMP_FILE=""
if [[ "${BACKUP_FILE}" == *.gz ]]; then
    log "Decompressing backup file..."
    TEMP_FILE=$(mktemp)
    gunzip -c "${BACKUP_FILE}" > "${TEMP_FILE}"
    RESTORE_FILE="${TEMP_FILE}"
else
    RESTORE_FILE="${BACKUP_FILE}"
fi

# Stop the bot to prevent connections during restore
log "Stopping bot container..."
docker-compose stop app

# Restore database
log "Restoring database..."
if docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" "${DB_NAME}" && \
   docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" "${DB_NAME}" < "${RESTORE_FILE}"; then
    log "Database restored successfully"
else
    log "ERROR: Restore failed!"
    # Cleanup temp file
    [ -n "${TEMP_FILE}" ] && rm -f "${TEMP_FILE}"
    exit 1
fi

# Cleanup temp file
[ -n "${TEMP_FILE}" ] && rm -f "${TEMP_FILE}"

# Start the bot again
log "Starting bot container..."
docker-compose start app

log "Restore process completed successfully!"
log "Please verify that the bot is working correctly."