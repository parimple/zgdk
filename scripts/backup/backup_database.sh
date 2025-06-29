#!/bin/bash
# Database backup script for zgdk bot

# Configuration
BACKUP_DIR="/home/ubuntu/backups/zgdk"
CONTAINER_NAME="zgdk-db-1"
DB_NAME="postgres"
DB_USER="postgres"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="zgdk_backup_${TIMESTAMP}.sql"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Starting database backup..."

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log "ERROR: Database container ${CONTAINER_NAME} is not running!"
    exit 1
fi

# Create backup
log "Creating backup: ${BACKUP_FILE}"
if docker exec "${CONTAINER_NAME}" pg_dump -U "${DB_USER}" "${DB_NAME}" > "${BACKUP_DIR}/${BACKUP_FILE}"; then
    log "Backup created successfully"
    
    # Compress backup
    log "Compressing backup..."
    gzip "${BACKUP_DIR}/${BACKUP_FILE}"
    log "Backup compressed: ${BACKUP_FILE}.gz"
    
    # Calculate size
    SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}.gz" | cut -f1)
    log "Backup size: ${SIZE}"
else
    log "ERROR: Backup failed!"
    exit 1
fi

# Clean up old backups
log "Cleaning up old backups (older than ${RETENTION_DAYS} days)..."
find "${BACKUP_DIR}" -name "zgdk_backup_*.sql.gz" -mtime +${RETENTION_DAYS} -exec rm {} \; -print | while read file; do
    log "Deleted old backup: $(basename "$file")"
done

# List current backups
BACKUP_COUNT=$(find "${BACKUP_DIR}" -name "zgdk_backup_*.sql.gz" | wc -l)
log "Current backup count: ${BACKUP_COUNT}"

# Optional: Copy to remote storage
# Example for S3:
# aws s3 cp "${BACKUP_DIR}/${BACKUP_FILE}.gz" s3://your-bucket/zgdk-backups/

log "Backup process completed successfully!"