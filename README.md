# Anaroma – Odoo 19 Community

## Gereksinim
- Docker ve Docker Compose

## İlk kurulum
```bash
./scripts/init_db.sh          # "anaroma" veritabanını oluşturur, tüm uygulamaları kurar
```
Tarayıcıda: http://localhost:8069 — kullanıcı `admin`, şifre `admin` (ilk girişte değiştir).

Kurulanlar: Community'deki tüm uygulamalar (CRM, Satış, Satın Alma, Stok, Üretim,
Faturalama, POS, Web Sitesi, E-ticaret, Proje, İK, …), Türkiye yerelleştirmesi
(`l10n_tr`) ve Türkçe dil. Demo veri yüklenmez.

## Günlük kullanım
```bash
docker compose up -d                    # başlat
docker compose logs -f odoo             # logları izle
docker compose restart odoo             # Python kodu değişince
docker compose run --rm odoo odoo -d anaroma -u <modul> --stop-after-init   # modül güncelle
docker compose down                     # durdur (veriler korunur)
docker compose down -v                  # durdur ve TÜM verileri sil
```

## Klasörler
| Klasör | İçerik |
|---|---|
| `addons/` | Kendi modüllerimiz (ve ileride OCA modülleri) |
| `config/odoo.conf` | Odoo ayarları |
| `scripts/` | Kurulum yardımcıları |
