#!/bin/sh
set -eu

backup_dir="${BACKUP_DIR:-./backups}"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
umask 077
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="$backup_dir/erp_intel-$timestamp.dump"
temporary_file="$backup_file.tmp"

if ! docker compose exec -T db pg_dump -U erp_intel -d erp_intel -Fc > "$temporary_file"; then
    rm -f "$temporary_file"
    printf 'Database backup failed.\n' >&2
    exit 1
fi
mv "$temporary_file" "$backup_file"
printf 'Created %s\n' "$backup_file"
