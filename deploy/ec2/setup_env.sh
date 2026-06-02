#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/ec2-user/howsyourday}"

cd "$APP_DIR"

jwt_secret="$(openssl rand -hex 32)"

cat > .env <<EOF
DATABASE_URL=postgresql+psycopg://hows_your_day:hows_your_day@localhost:5432/hows_your_day
JWT_SECRET_KEY=$jwt_secret
NEXT_PUBLIC_API_BASE_URL=/api
HYS_DISABLE_TMAP=true
HYS_ROUTE_PROVIDER=osrm
OSRM_BASE_URL=https://router.project-osrm.org
OSRM_PROFILE=foot
HYS_DISABLE_LLM=false
EOF

if [[ -f apps/web/.env.local ]]; then
  if grep -q '^NEXT_PUBLIC_API_BASE_URL=' apps/web/.env.local; then
    sed -i 's#^NEXT_PUBLIC_API_BASE_URL=.*#NEXT_PUBLIC_API_BASE_URL=/api#' apps/web/.env.local
  else
    printf '\nNEXT_PUBLIC_API_BASE_URL=/api\n' >> apps/web/.env.local
  fi
else
  printf 'NEXT_PUBLIC_API_BASE_URL=/api\n' > apps/web/.env.local
fi

chmod 600 .env apps/web/.env.local
printf 'env-ready\n'
