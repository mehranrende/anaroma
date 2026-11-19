#!/usr/bin/env bash
# Yeni bir veritabani olusturur ve Community'deki tum uygulamalari kurar.
# Kullanim: ./scripts/init_db.sh [veritabani_adi]   (varsayilan: anaroma)
set -euo pipefail
# Windows Git Bash: /mnt/... yollarini Windows yoluna cevirmesin
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")/.."

DB="${1:-anaroma}"

docker compose up -d db
APPS=$(docker compose run --rm --no-deps -T odoo python3 /mnt/scripts/install_apps.py)
echo "Kurulacak uygulamalar: $APPS"

docker compose run --rm -T odoo odoo \
  -d "$DB" \
  -i "$APPS" \
  --without-demo=True \
  --load-language=tr_TR \
  --stop-after-init

docker compose up -d odoo
echo
echo "Hazir: http://localhost:8069  (veritabani: $DB, kullanici: admin, sifre: admin)"
