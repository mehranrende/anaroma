# Anaroma – Odoo 19 Community

## Gereksinim
- Docker ve Docker Compose

## İlk kurulum
```bash
./scripts/init_db.sh          # "anaroma" veritabanını oluşturur, tüm uygulamaları kurar
```
Tarayıcıda: http://localhost:8069 — kullanıcı `admin`, şifre `admin` (ilk girişte değiştir).

Kurulanlar: Community'deki tüm uygulamalar (CRM, Satış, Satın Alma, Stok, Üretim,
Faturalama, POS, Web Sitesi, E-ticaret, Proje, İK, …), `addons/` altındaki kendi
modüllerimiz, Türkiye şirketi (TRY, Türkiye hesap planı ve KDV) ve Türkçe dil.
Demo veri yüklenmez. Veritabanı zaten varsa betik hiçbir şeye dokunmadan durur.

## Modüller

### `anaroma_formula` – Formülasyon
Menü: **Formülasyon**
- **Hammaddeler:** CAS no, yoğunluk (L/ml ile alınanlar için), birden çok tedarikçi
- **Tedarikçi Fiyatları:** her tedarikçi için ülke, minimum miktar, para birimi,
  satın alma birimi (kg, g, L, Bidon 25 kg, Varil 200 kg…) ve güncel kurla **TL/kg** karşılaştırması
- **Formüller:** aroma/esans için hammadde + ağırlık (g), otomatik %, parti büyüklüğü (kg)
  - Maliyet: minimum miktar kademesine, döviz kuruna ve birim dönüşümüne göre kg ve parti maliyeti
  - Yöntem: *En ucuz tedarikçi* veya *Öncelikli tedarikçi*; satırda sabit tedarikçi seçilebilir
  - Alt formül: bir esans başka bir aromayı hammadde olarak kullanabilir
  - Onay → MRP **Üretim Reçetesi** otomatik oluşur; onaylı formül kilitlenir
  - **Yeni Versiyon** → v2, v3…; yenisi onaylanınca eskisi "Eski" olur, reçetesi arşivlenir
- **Yetki:** formüller ticari sır; sadece *Formülasyon / Kullanıcı* (görür) ve
  *Yönetici* (yazar, onaylar) gruplarındakiler erişir. Ayarlar > Kullanıcılar'dan verilir.
- **Döviz kurları:** Formülasyon > Yapılandırma > Para Birimleri ve Kurlar (Community'de elle girilir)

Testler:
```bash
docker compose run --rm odoo odoo -d anaroma -u anaroma_formula --test-tags /anaroma_formula --stop-after-init
```

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
