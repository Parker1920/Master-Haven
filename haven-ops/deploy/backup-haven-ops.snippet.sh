# ── Haven Ops backup — APPEND this block to /usr/local/bin/backup-haven.sh ──
# (Parker runs this on the Pi; it reuses the script's existing $BACKUP_DIR
#  and $DATE variables and its 7-day *.db retention sweep.)
#
# The DB is WAL-mode SQLite: NEVER raw-`cp` it — a copy taken mid-write is
# corrupt. `.backup` takes a consistent snapshot while the app keeps running.
OPS_DATA="/home/pi8gb/docker/haven-ops-data"
sqlite3 "$OPS_DATA/haven-ops.db" ".backup '$BACKUP_DIR/haven_ops_$DATE.db'"

# Frozen generated documents: immutable PDFs, new files only — a plain mirror
# is a complete backup (nothing is ever rewritten in place).
rsync -a "$OPS_DATA/uploads/" "$BACKUP_DIR/haven-ops-uploads/"

# The e-signature + env are placed by hand and tiny — keep copies too.
cp -n "$OPS_DATA/signature.png" "$BACKUP_DIR/haven-ops-signature.png" 2>/dev/null
echo "$(date): Backup created: haven_ops_$DATE.db" >> /var/log/haven-backup.log

# If the Pi host lacks the sqlite3 CLI, snapshot through the container instead:
#   docker exec haven-ops python -c "import sqlite3; s=sqlite3.connect('/data/haven-ops.db'); d=sqlite3.connect('/data/backup_tmp.db'); s.backup(d); d.close(); s.close()"
#   mv "$OPS_DATA/backup_tmp.db" "$BACKUP_DIR/haven_ops_$DATE.db"
