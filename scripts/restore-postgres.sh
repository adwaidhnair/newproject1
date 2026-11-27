#!/bin/sh
set -eu

backup_file="${1:-}"
if [ -z "$backup_file" ] || [ ! -f "$backup_file" ]; then
    printf 'Usage: %s <backup.dump>\n' "$0" >&2
    exit 2
fi
if [ "${CONFIRM_DATABASE_RESTORE:-}" != "yes" ]; then
    printf 'This replaces the current ERP database. Re-run with CONFIRM_DATABASE_RESTORE=yes after verifying the backup.\n' >&2
    exit 2
fi

docker compose exec -T db pg_restore \
    --clean --if-exists --no-owner --exit-on-error \
    -U erp_intel -d erp_intel < "$backup_file"
printf 'Restore completed from %s\n' "$backup_file"
