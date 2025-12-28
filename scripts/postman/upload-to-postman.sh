#!/bin/bash
# Upload Postman collection (non-interactive, overwrite existing)
# Usage:
#   POSTMAN_API_KEY=... scripts/postman/upload-to-postman.sh
# Optional:
#   POSTMAN_COLLECTION_FILE=... (defaults to postman_collection.json at repo root)
#   POSTMAN_COLLECTION_NAME=... (defaults to collection info.name)
#   POSTMAN_ENV_FILE=... or POSTMAN_ENV_FILES=comma,separated,paths

set -euo pipefail

POSTMAN_API_BASE="https://api.getpostman.com"
COLLECTIONS_ENDPOINT="$POSTMAN_API_BASE/collections"
ENVIRONMENTS_ENDPOINT="$POSTMAN_API_BASE/environments"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
API_KEY_FILE="$HOME/.postman-api-key"
# Files
COLLECTION_FILE="${POSTMAN_COLLECTION_FILE:-$PROJECT_ROOT/postman_collection.json}"
COLLECTION_NAME="${POSTMAN_COLLECTION_NAME:-}"
ENV_FILES=("$PROJECT_ROOT/postman_environment.json")

if [ -n "${POSTMAN_ENV_FILE:-}" ]; then
  ENV_FILES+=("$POSTMAN_ENV_FILE")
fi
if [ -n "${POSTMAN_ENV_FILES:-}" ]; then
  IFS=',' read -r -a _ENV_SPLIT <<< "$POSTMAN_ENV_FILES"
  ENV_FILES+=("${_ENV_SPLIT[@]}")
fi

log() { echo "[$(date '+%H:%M:%S')] $*"; }
err() { echo "[$(date '+%H:%M:%S')] ERROR: $*" >&2; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { err "Missing '$1'. Install it first."; exit 1; }
}

read_stored_key() {
  [ -f "$API_KEY_FILE" ] && base64 -d <"$API_KEY_FILE" 2>/dev/null || true
}

store_key() {
  echo -n "$1" | base64 >"$API_KEY_FILE"
  chmod 600 "$API_KEY_FILE"
}

get_api_key() {
  if [ -n "${POSTMAN_API_KEY:-}" ]; then
    echo "$POSTMAN_API_KEY"
    return
  fi
  if [ -n "${1:-}" ]; then
    echo "$1"
    return
  fi
  local stored
  stored=$(read_stored_key)
  if [ -n "$stored" ]; then
    echo "$stored"
    return
  fi
  err "No Postman API key provided. Set POSTMAN_API_KEY or pass as arg."
  exit 1
}

api_request() {
  local method="$1" url="$2" api_key="$3" data="${4:-}"
  if [ -n "$data" ]; then
    curl -sS -X "$method" "$url" -H "X-API-Key: $api_key" -H "Content-Type: application/json" -d "$data"
  else
    curl -sS -X "$method" "$url" -H "X-API-Key: $api_key"
  fi
}

delete_collection_if_exists() {
  local api_key="$1" name="$2"
  local resp uid
  resp=$(api_request GET "$COLLECTIONS_ENDPOINT" "$api_key")
  uid=$(echo "$resp" | jq -r --arg NAME "$name" '.collections[]? | select(.name==$NAME) | .uid' 2>/dev/null || true)
  if [ -n "$uid" ] && [ "$uid" != "null" ]; then
    log "Deleting existing collection '$name' (uid: $uid)"
    api_request DELETE "$COLLECTIONS_ENDPOINT/$uid" "$api_key" >/dev/null
  fi
}

upload_collection() {
  local api_key="$1" file="$2" name="$3"
  [ -f "$file" ] || { err "Collection file not found: $file"; exit 1; }
  local data wrapped
  data=$(jq ".info.name = \"$name\" | del(.info._postman_id)" "$file")
  wrapped="{\"collection\": $data}"
  local resp
  resp=$(api_request POST "$COLLECTIONS_ENDPOINT" "$api_key" "$wrapped")
  if echo "$resp" | jq -e '.collection.uid' >/dev/null 2>&1; then
    local uid
    uid=$(echo "$resp" | jq -r '.collection.uid')
    log "Uploaded collection '$name' (uid: $uid)"
  else
    err "Failed to upload collection. Response: $resp"
    exit 1
  fi
}

env_name_from_file() {
  local file="$1"
  jq -r '.name // empty' "$file"
}

delete_environment_if_exists() {
  local api_key="$1" name="$2"
  local resp uid
  resp=$(api_request GET "$ENVIRONMENTS_ENDPOINT" "$api_key")
  uid=$(echo "$resp" | jq -r --arg NAME "$name" '.environments[]? | select(.name==$NAME) | .uid' 2>/dev/null || true)
  if [ -n "$uid" ] && [ "$uid" != "null" ]; then
    log "Deleting existing environment '$name' (uid: $uid)"
    api_request DELETE "$ENVIRONMENTS_ENDPOINT/$uid" "$api_key" >/dev/null
  fi
}

upload_environment() {
  local api_key="$1" file="$2" name="$3"
  [ -f "$file" ] || { err "Environment file not found: $file"; exit 1; }
  local data wrapped
  data=$(jq ".name = \"$name\" | del(.id) | del(._postman_id)" "$file")
  wrapped="{\"environment\": $data}"
  local resp
  resp=$(api_request POST "$ENVIRONMENTS_ENDPOINT" "$api_key" "$wrapped")
  if echo "$resp" | jq -e '.environment.uid' >/dev/null 2>&1; then
    local uid
    uid=$(echo "$resp" | jq -r '.environment.uid')
    log "Uploaded environment '$name' (uid: $uid)"
  else
    err "Failed to upload environment '$name'. Response: $resp"
    exit 1
  fi
}

maybe_upload_environment() {
  local api_key="$1" file="$2"
  if [ ! -f "$file" ]; then
    log "Skip environment upload (file not found): $file"
    return
  fi
  local name
  name=$(env_name_from_file "$file")
  if [ -z "$name" ]; then
    err "Environment file missing name: $file"
    exit 1
  fi
  delete_environment_if_exists "$api_key" "$name"
  upload_environment "$api_key" "$file" "$name"
}

main() {
  require_cmd jq
  require_cmd curl

  local api_key
  api_key=$(get_api_key "${1:-}")
  store_key "$api_key"

  if [ -z "$COLLECTION_NAME" ]; then
    COLLECTION_NAME=$(jq -r '.info.name // empty' "$COLLECTION_FILE")
  fi
  if [ -z "$COLLECTION_NAME" ]; then
    err "Collection name missing. Set POSTMAN_COLLECTION_NAME or ensure info.name exists in the collection JSON."
    exit 1
  fi

  delete_collection_if_exists "$api_key" "$COLLECTION_NAME"
  upload_collection "$api_key" "$COLLECTION_FILE" "$COLLECTION_NAME"

  for env_file in "${ENV_FILES[@]:-}"; do
    [ -n "$env_file" ] || continue
    maybe_upload_environment "$api_key" "$env_file"
  done
}

main "$@"
