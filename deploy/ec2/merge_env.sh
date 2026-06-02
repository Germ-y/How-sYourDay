#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/ec2-user/howsyourday}"
API_ENV="$APP_DIR/.env"
WEB_ENV="$APP_DIR/apps/web/.env.local"

set_env() {
  local file="$1"
  local key="$2"
  local value="$3"

  if grep -q "^${key}=" "$file"; then
    sed -i "s#^${key}=.*#${key}=${value}#" "$file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$file"
  fi
}

cd "$APP_DIR"

existing_jwt=""
if [[ -f "$API_ENV" ]]; then
  existing_jwt="$(grep '^JWT_SECRET_KEY=' "$API_ENV" | tail -1 | cut -d= -f2- || true)"
  cp "$API_ENV" "$API_ENV.before-secret-sync"
fi

if [[ -f "$API_ENV.incoming" ]]; then
  mv "$API_ENV.incoming" "$API_ENV"
fi

if [[ -z "$existing_jwt" ]]; then
  existing_jwt="$(openssl rand -hex 32)"
fi

set_env "$API_ENV" "DATABASE_URL" "postgresql+psycopg://hows_your_day:hows_your_day@localhost:5432/hows_your_day"
set_env "$API_ENV" "JWT_SECRET_KEY" "$existing_jwt"
set_env "$API_ENV" "NEXT_PUBLIC_API_BASE_URL" "/api"
set_env "$API_ENV" "HYS_DISABLE_TMAP" "true"
set_env "$API_ENV" "HYS_ROUTE_PROVIDER" "osrm"
set_env "$API_ENV" "OSRM_BASE_URL" "https://router.project-osrm.org"
set_env "$API_ENV" "OSRM_PROFILE" "foot"

if ! grep -q '^HYS_DISABLE_LLM=' "$API_ENV"; then
  printf 'HYS_DISABLE_LLM=false\n' >> "$API_ENV"
fi

if [[ -f "$WEB_ENV.incoming" ]]; then
  mv "$WEB_ENV.incoming" "$WEB_ENV"
elif [[ ! -f "$WEB_ENV" ]]; then
  touch "$WEB_ENV"
fi

set_env "$WEB_ENV" "NEXT_PUBLIC_API_BASE_URL" "/api"

chmod 600 "$API_ENV" "$WEB_ENV"
printf 'env-merged\n'
