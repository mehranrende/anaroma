#!/usr/bin/env bash
# Yeni bir veritabani olusturur ve Community'deki tum uygulamalari kurar.
# Sirket ulkesi Turkiye: para birimi TRY, Turkiye hesap plani ve KDV, Turkce arayuz.
# Kullanim: ./scripts/init_db.sh [veritabani_adi]   (varsayilan: anaroma)
# Veritabani zaten varsa hata verir, mevcut veriye dokunmaz.
set -euo pipefail
# Windows Git Bash: /mnt/... yollarini Windows yoluna cevirmesin
export MSYS_NO_PATHCONV=1
cd "$(dirname "$0")/.."

DB="${1:-anaroma}"

docker compose up -d db

# 1) Bos veritabani: sirket Turkiye'de, dil Turkce
docker compose run --rm -T --entrypoint odoo odoo db -c /etc/odoo/odoo.conf \
  init "$DB" --country TR --language tr_TR

# 2) Tum uygulamalar + addons/ altindaki kendi modullerimiz
APPS=$(docker compose run --rm --no-deps -T odoo python3 /mnt/scripts/install_apps.py)
echo "Kurulacak uygulamalar: $APPS"

docker compose run --rm -T odoo odoo \
  -d "$DB" \
  -i "$APPS" \
  --without-demo=True \
  --stop-after-init

docker compose up -d odoo
echo
echo "Hazir: http://localhost:8069  (veritabani: $DB, kullanici: admin, sifre: admin)"
