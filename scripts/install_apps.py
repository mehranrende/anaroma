"""Odoo Community'deki tum uygulamalarin (application=True) listesini basar.

Container icinde calisir; cikti `odoo -i` parametresine verilir.
Tum *modulleri* degil tum *uygulamalari* kurariz: test modulleri ve
yuzlerce ulke yerellestirmesi (l10n_*) veritabanini sisirir ve catisir.
Bagimli teknik moduller Odoo tarafindan otomatik kurulur.
"""
import ast
import pathlib

ADDONS = pathlib.Path("/usr/lib/python3/dist-packages/odoo/addons")
EXTRA = ["l10n_tr"]  # Turkiye hesap plani ve vergileri

apps = []
for manifest in sorted(ADDONS.glob("*/__manifest__.py")):
    data = ast.literal_eval(manifest.read_text())
    name = manifest.parent.name
    if not data.get("application") or not data.get("installable", True):
        continue
    if name.startswith(("test_", "l10n_")):
        continue
    apps.append(name)

print(",".join(apps + EXTRA))
