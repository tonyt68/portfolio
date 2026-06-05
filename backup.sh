#!/bin/zsh
# Backup ~/dev to ~/backups with datestamp

BACKUP_DIR="$HOME/backups"
mkdir -p "$BACKUP_DIR"

FILENAME="tonyai-dev-$(date +%Y%m%d-%H%M%S).zip"

find "$HOME/dev" -type f \
  ! -path "*/.git/*" \
  ! -path "*/node_modules/*" \
  ! -path "*/__pycache__/*" \
  ! -path "*/.venv/*" \
  ! -path "*/venv/*" \
  ! -path "*/bin/*" \
  ! -path "*/.terraform/*" \
  ! -name "*.zip" \
  | zip "$BACKUP_DIR/$FILENAME" -@

echo "Backup saved: $BACKUP_DIR/$FILENAME"
