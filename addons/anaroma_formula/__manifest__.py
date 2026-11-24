{
    "name": "Anaroma Formülasyon",
    "summary": "Aroma ve esans formülleri, hammadde tedarikçileri ve formül maliyeti",
    "description": """
Aroma ve esans ürünleri için formül (reçete) yönetimi:

* Hammadde kartı: CAS no, yoğunluk, birden çok tedarikçi
* Tedarikçi fiyatları: ülke, minimum miktar, para birimi, satın alma birimi
  (kg, g, L, bidon, varil...) ve TL/kg karşılaştırması
* Formül: hammadde + ağırlık (g), yüzde, parti büyüklüğü, versiyonlama
* Maliyet: tedarikçi fiyat kademeleri, döviz kuru ve birim dönüşümüyle kg maliyeti
* Onaylanan formülden otomatik Üretim Reçetesi (MRP BoM)
""",
    "version": "19.0.1.0.0",
    "category": "Manufacturing",
    "author": "Anaroma",
    "license": "LGPL-3",
    "depends": ["purchase", "mrp", "mail"],
    "data": [
        "security/anaroma_security.xml",
        "security/ir.model.access.csv",
        "data/anaroma_data.xml",
        "views/anaroma_formula_views.xml",
        "views/product_views.xml",
        "views/product_supplierinfo_views.xml",
        "views/mrp_bom_views.xml",
        "views/menus.xml",
    ],
    "application": True,
    "installable": True,
}
