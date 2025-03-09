 #!/bin/bash
BACKUP_DIR="/mount/nvme/Hosted_Services/backups/Bitcoin_Tracker_backup"
BACKUP_FILE_NAME="$(date +"%d-%m-%y-%H%M%S.sql")"
docker exec bitcointracker_db bash -c 'exec mysqldump --databases bitcointracker -u"root" -p"4493abcd"' > "$BACKUP_DIR"/"$BACKUP_FILE_NAME";
find "$BACKUP_DIR" -type f -name "*.sql" -mtime +15 -delete
