# Database Backup System for ZGDK Bot

This directory contains scripts for automated database backups and restoration.

## 🔧 Setup

### 1. Configure Automatic Backups

Run the setup script to configure automatic backups via cron:

```bash
./setup_cron.sh
```

You'll be prompted to choose a backup schedule:
- Every 6 hours
- Daily at 3 AM
- Daily at custom time
- Custom cron expression

### 2. Manual Backup

To create a backup manually:

```bash
./backup_database.sh
```

## 📁 Backup Location

Backups are stored in: `/home/ubuntu/backups/zgdk/`

Format: `zgdk_backup_YYYYMMDD_HHMMSS.sql.gz`

## 🔄 Restore Process

### Restore from Backup

```bash
# List available backups
./restore_database.sh

# Restore specific backup
./restore_database.sh zgdk_backup_20250628_030000.sql.gz

# Or with full path
./restore_database.sh /home/ubuntu/backups/zgdk/zgdk_backup_20250628_030000.sql.gz
```

⚠️ **WARNING**: Restoring will replace ALL current data in the database!

## 🔍 Monitoring

### View Backup Logs
```bash
tail -f /home/ubuntu/logs/zgdk_backup.log
```

### Check Cron Jobs
```bash
crontab -l
```

### List Backups
```bash
ls -lh /home/ubuntu/backups/zgdk/
```

## ⚙️ Configuration

Edit the scripts to modify:
- `BACKUP_DIR`: Where backups are stored
- `RETENTION_DAYS`: How many days to keep backups (default: 7)
- `CONTAINER_NAME`: Database container name
- `DB_NAME`: Database name
- `DB_USER`: Database user

## 🚨 Important Notes

1. **Disk Space**: Monitor available disk space, especially with frequent backups
2. **Retention**: Old backups are automatically deleted after 7 days
3. **Bot Downtime**: During restore, the bot will be temporarily stopped
4. **Permissions**: Ensure scripts have execute permissions (`chmod +x *.sh`)

## 🔐 Security Recommendations

1. **Encrypt Backups**: For sensitive data, consider encrypting backups:
   ```bash
   # Add to backup script:
   openssl enc -aes-256-cbc -salt -in backup.sql -out backup.sql.enc -k YOUR_PASSWORD
   ```

2. **Remote Storage**: Consider copying backups to remote storage (S3, Google Drive, etc.)

3. **Access Control**: Restrict access to backup directory:
   ```bash
   chmod 700 /home/ubuntu/backups/zgdk/
   ```

## 🆘 Troubleshooting

### Container Not Found
```
ERROR: Database container zgdk-db-1 is not running!
```
Solution: Ensure Docker containers are running: `docker-compose up -d`

### Permission Denied
```
bash: ./backup_database.sh: Permission denied
```
Solution: `chmod +x *.sh`

### No Space Left
Monitor disk space: `df -h`
Clean old backups manually if needed: `rm /home/ubuntu/backups/zgdk/zgdk_backup_*.sql.gz`