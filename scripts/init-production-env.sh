#!/bin/sh
set -eu

domain="${1:-}"
if [ -z "$domain" ]; then
    printf 'Usage: %s <public-domain>\n' "$0" >&2
    exit 2
fi
case "$domain" in
    *[!A-Za-z0-9.-]*|.*|*.) printf 'Invalid DNS hostname: %s\n' "$domain" >&2; exit 2 ;;
esac
if [ -e .env ]; then
    printf '.env already exists; refusing to overwrite secrets.\n' >&2
    exit 1
fi
if ! command -v openssl >/dev/null 2>&1; then
    printf 'openssl is required to generate deployment secrets.\n' >&2
    exit 1
fi

umask 077
{
    printf 'APP_DOMAIN=%s\n' "$domain"
    printf 'CORS_ORIGINS=https://%s\n' "$domain"
    printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 32)"
    printf 'APP_DB_PASSWORD=%s\n' "$(openssl rand -hex 32)"
    printf 'AUTH_TOKEN_SECRET=%s\n' "$(openssl rand -hex 32)"
    printf 'BOOTSTRAP_SETUP_TOKEN=%s\n' "$(openssl rand -hex 32)"
} > .env
chmod 600 .env

printf 'Wrote .env with unique secrets and mode 600.\n'
printf 'Store the owner setup token securely; retrieve it on the host with:\n'
printf "  sed -n 's/^BOOTSTRAP_SETUP_TOKEN=//p' .env\n"
