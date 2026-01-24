#!/usr/bin/env bash
set -euo pipefail

# --- 1. Find psql ---
PSQL="psql"
if ! command -v psql &> /dev/null; then
  # Check common Postgres.app paths
  if [ -f "/Applications/Postgres.app/Contents/Versions/latest/bin/psql" ]; then
    PSQL="/Applications/Postgres.app/Contents/Versions/latest/bin/psql"
  elif [ -d "/Applications/Postgres.app/Contents/Versions" ]; then
     # Try to find the latest version directory
     LATEST_VER=$(ls -1 /Applications/Postgres.app/Contents/Versions | sort -n | tail -1)
     if [ -n "$LATEST_VER" ] && [ -f "/Applications/Postgres.app/Contents/Versions/$LATEST_VER/bin/psql" ]; then
        PSQL="/Applications/Postgres.app/Contents/Versions/$LATEST_VER/bin/psql"
     fi
  fi
fi

if ! command -v "$PSQL" &> /dev/null && [ ! -x "$PSQL" ]; then
  echo "Error: psql not found. Please ensure Postgres.app is installed and running."
  exit 1
fi

echo "Using psql: $PSQL"

# --- 2. Parse config.yaml ---
CONFIG_FILE="config.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
  echo "Error: $CONFIG_FILE not found."
  exit 1
fi

# Simple grep/awk parsing (assumes simple structure as seen in file)
get_config() {
  key=$1
  grep -A 10 "^db:" "$CONFIG_FILE" | grep "^  $key:" | awk -F': ' '{print $2}' | tr -d '"' | sed 's/ *#.*//'
}

DB_HOST=$(get_config "host")
DB_PORT=$(get_config "port")
DB_NAME=$(get_config "database")
DB_USER=$(get_config "user")
DB_PASS=$(get_config "password")

: "${DB_HOST:=localhost}"
: "${DB_PORT:=5432}"
: "${DB_NAME:=paperweight}"
: "${DB_USER:=paperweight}"

# Validate DB_USER and DB_NAME to prevent SQL injection (alphanumeric and underscores only)
if ! [[ "$DB_USER" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
  echo "Error: DB_USER must be alphanumeric (with underscores). Got: '$DB_USER'"
  exit 1
fi
if ! [[ "$DB_NAME" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
  echo "Error: DB_NAME must be alphanumeric (with underscores). Got: '$DB_NAME'"
  exit 1
fi

echo "Config: Host=$DB_HOST Port=$DB_PORT DB=$DB_NAME User=$DB_USER"

# --- 3. Create Role/DB if missing ---
# We try to connect to 'postgres' database with current system user to do admin tasks
# This assumes the current system user has superuser access (default in Postgres.app)

echo "Checking if role '$DB_USER' exists..."
if ! "$PSQL" -h "$DB_HOST" -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
  echo "Creating role '$DB_USER'..."
  "$PSQL" -h "$DB_HOST" -d postgres -v pw="$DB_PASS" -c "CREATE USER $DB_USER WITH PASSWORD :'pw';"
else
  echo "Role '$DB_USER' already exists."
fi

echo "Checking if database '$DB_NAME' exists..."
if ! "$PSQL" -h "$DB_HOST" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
  echo "Creating database '$DB_NAME'..."
  "$PSQL" -h "$DB_HOST" -d postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
else
  echo "Database '$DB_NAME' already exists."
fi

# --- 4. Install Extensions (as superuser) ---
echo "Installing extensions..."
"$PSQL" -h "$DB_HOST" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# --- 5. Run Schema ---
echo "Applying schema..."

# Use a temporary .pgpass file instead of PGPASSWORD environment variable.
# This avoids exposing the password via /proc or process listings.
PGPASS_TMP=$(mktemp)
chmod 600 "$PGPASS_TMP"
trap 'rm -f "$PGPASS_TMP"' EXIT

# .pgpass format: hostname:port:database:username:password
echo "$DB_HOST:$DB_PORT:$DB_NAME:$DB_USER:$DB_PASS" > "$PGPASS_TMP"

PGPASSFILE="$PGPASS_TMP" "$PSQL" -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -f "docs/db_schema.sql"

echo "Database initialization complete!"
