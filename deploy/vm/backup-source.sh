#!/usr/bin/env bash
# Nightly source-code backup for the shared dev VM (no Git/GitHub = this is your history and safety net).
#   * dated .tar.gz of the project (excludes node_modules, .venv, build output, local data, secrets)
#   * kept locally for KEEP_LOCAL_DAYS, and uploaded to a private, immutable blob container
# Cron (root, installed by setup-dev-vm.sh): 15 2 * * *  ff-backup nightly   (destination: BACKUP_ACCOUNT in /etc/default/ff-backup)
# Manual snapshot before risky work:   sudo ff-backup "before-refactor"
set -euo pipefail
FF_ROOT="${FF_ROOT:-/srv/ff}"
LABEL="${1:-nightly}"; LABEL="$(echo "$LABEL" | tr -c 'A-Za-z0-9._-' '-')"
KEEP_LOCAL_DAYS="${KEEP_LOCAL_DAYS:-14}"
BACKUP_DIR="$FF_ROOT/backups"; mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="$BACKUP_DIR/ff-source-$STAMP-$LABEL.tar.gz"
tar --exclude='node_modules' --exclude='.venv' --exclude='__pycache__' --exclude='dist' --exclude='build' \
    --exclude='data' --exclude='.env' --exclude='.env.*' -czf "$FILE" -C "$FF_ROOT" project
( cd "$BACKUP_DIR" && sha256sum "$(basename "$FILE")" > "$(basename "$FILE").sha256" )
chmod 640 "$FILE" "$FILE.sha256"
echo "Local backup: $FILE ($(du -h "$FILE" | cut -f1))"
find "$BACKUP_DIR" -name 'ff-source-*' -type f -mtime +"$KEEP_LOCAL_DAYS" -delete

# Off-VM copy (set BACKUP_ACCOUNT; the VM's managed identity needs 'Storage Blob Data Contributor' on that account)
if [ -n "${BACKUP_ACCOUNT:-}" ]; then
  az login --identity --output none
  for f in "$FILE" "$FILE.sha256"; do
    az storage blob upload --auth-mode login --account-name "$BACKUP_ACCOUNT" \
       --container-name "${BACKUP_CONTAINER:-source-backups}" --file "$f" --name "$(basename "$f")" --no-progress --output none
  done
  echo "Uploaded to $BACKUP_ACCOUNT/${BACKUP_CONTAINER:-source-backups}"
else
  echo "BACKUP_ACCOUNT not set: local copy only."
fi
