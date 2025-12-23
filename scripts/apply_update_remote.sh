#!/bin/bash
set -e
# Remote update script applied on the Pi. Assumes archive is at /tmp/Master-Haven-update.tar.gz
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/home/parker/Master-Haven-backup-${TIMESTAMP}
echo "Creating backup: ${BACKUP_DIR}"
cp -a /home/parker/Master-Haven ${BACKUP_DIR} || echo 'backup failed — continuing'
# Extract archive into a temporary folder and sync to repo
mkdir -p /tmp/Master-Haven
tar -xzf /tmp/Master-Haven-update.tar.gz -C /tmp/Master-Haven
rsync -av --delete /tmp/Master-Haven/ /home/parker/Master-Haven/
echo 'Files updated. Please restart the Haven UI server on the Pi.'
