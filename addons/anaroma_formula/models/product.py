from odoo import api, fields, models

ANAROMA_KINDS = [
    ("raw", "Hammadde"),
    ("aroma", "Aroma"),
    ("essence", "Esans"),
]


class ProductTemplate(models.Model):
    _inherit = "product.template"

    anaroma_kind = fields.Selection(
        ANAROMA_KINDS, string="Anaroma Türü", index=True,
        help="Hammadde: formüllerde kullanılan girdi.\n"
             "Aroma / Esans: formülle üretilen ürün.",
    )
    cas_number = fields.Char("CAS No")
    anaroma_density = fields.Float(
        "Yoğunluk (g/ml)", digits=(12, 4),
        help="Litre / ml ile satın alınan hammaddelerin kg'a çevrilmesi için gerekli.",
    )
    anaroma_formula_ids = fields.One2many("anaroma.formula", "product_tmpl_id", string="Formüller")
    anaroma_formula_count = fields.Integer(compute="_compute_anaroma_formula_count")
    anaroma_current_formula_id = fields.Many2one(
        "anaroma.formula", string="Geçerli Formül", compute="_compute_anaroma_current_formula",
    )
    anaroma_used_in_count = fields.Integer(compute="_compute_anaroma_used_in_count")

    def _compute_anaroma_formula_count(self):
        data = self.env["anaroma.formula"]._read_group(
            [("product_tmpl_id", "in", self.ids)], ["product_tmpl_id"], ["__count"])
        counts = {tmpl.id: count for tmpl, count in data}
        for tmpl in self:
            tmpl.anaroma_formula_count = counts.get(tmpl.id, 0)

    def _compute_anaroma_current_formula(self):
        for tmpl in self:
            tmpl.anaroma_current_formula_id = self.env["anaroma.formula"].search(
                [("product_tmpl_id", "=", tmpl.id), ("state", "=", "approved")],
                order="version desc", limit=1)

    def _compute_anaroma_used_in_count(self):
        data = self.env["anaroma.formula.line"]._read_group(
            [("product_tmpl_id", "in", self.ids)], ["product_tmpl_id"], ["formula_id:count_distinct"])
        counts = {tmpl.id: count for tmpl, count in data}
        for tmpl in self:
            tmpl.anaroma_used_in_count = counts.get(tmpl.id, 0)

    @api.model_create_multi
    def create(self, vals_list):
        kg = self.env.ref("uom.product_uom_kgm")
        for vals in vals_list:
            kind = vals.get("anaroma_kind") or self.env.context.get("default_anaroma_kind")
            if kind:
                # Aroma, esans ve hammaddeler stoklu ve varsayilan olarak kg ile tutulur
                vals.setdefault("type", "consu")
                vals.setdefault("is_storable", True)
                vals.setdefault("uom_id", kg.id)
            if kind == "raw":
                vals.setdefault("sale_ok", False)
                vals.setdefault("purchase_ok", True)
        return super().create(vals_list)

    def action_view_anaroma_formulas(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("anaroma_formula.action_anaroma_formula")
        action["domain"] = [("product_tmpl_id", "=", self.id)]
        action["context"] = {"default_product_tmpl_id": self.id}
        return action

    def action_view_anaroma_used_in(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id("anaroma_formula.action_anaroma_formula")
        action["domain"] = [("line_ids.product_tmpl_id", "=", self.id)]
        action["context"] = {}
        return action


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _anaroma_kg_per_uom(self, uom):
        """1 `uom` kac kg eder? Agirlik birimleri dogrudan, hacim birimleri
        urunun yogunluguyla cevrilir. Cevrilemiyorsa False doner."""
        self.ensure_one()
        if not uom:
            return False
        kg = self.env.ref("uom.product_uom_kgm")
        ml = self.env.ref("uom.product_uom_milliliter")
        if uom._has_common_reference(kg):
            return uom._compute_quantity(1.0, kg, round=False)
        if uom._has_common_reference(ml) and self.anaroma_density > 0:
            return uom._compute_quantity(1.0, ml, round=False) * self.anaroma_density / 1000.0
        return False

    def _anaroma_seller_cost_per_kg(self, seller, date=None):
        """Tedarikci fiyatini sirket para biriminde kg fiyatina cevirir."""
        self.ensure_one()
        kg_per_uom = self._anaroma_kg_per_uom(seller.product_uom_id)
        if not kg_per_uom:
            return False
        price = seller.price * (1 - (seller.discount or 0.0) / 100.0) / kg_per_uom
        company = seller.company_id or self.env.company
        return seller.currency_id._convert(
            price, company.currency_id, company, date or fields.Date.context_today(self), round=False)

    def _anaroma_cost_per_kg(self, qty_kg=0.0, seller=None, method="cheapest", date=None, _visited=None):
        """Hammaddenin kg maliyetini (sirket para birimi) hesaplar.

        Oncelik: secilen tedarikci > tedarikci fiyat listesi (minimum miktar
        kademelerine gore) > urunun gecerli formulu > urun maliyet fiyati.

        :param qty_kg: alinacak miktar (kg); tedarikci minimum miktarina gore kademe secer
        :param method: 'cheapest' (en ucuz kg fiyati) veya 'preferred' (listedeki sira)
        :return: dict(cost, seller, source, warning)
        """
        self.ensure_one()
        date = date or fields.Date.context_today(self)
        res = {"cost": 0.0, "seller": self.env["product.supplierinfo"], "source": "none", "warning": False}

        if seller:
            cost = self._anaroma_seller_cost_per_kg(seller, date)
            if cost is False:
                res["warning"] = "Tedarikçi birimi kg'a çevrilemiyor (yoğunluk girin)"
                return res
            res.update(cost=cost, seller=seller, source="seller")
            if seller.min_qty * self._anaroma_kg_per_uom(seller.product_uom_id) > qty_kg + 1e-9:
                res["warning"] = "Minimum alım miktarının altında"
            return res

        # quantity=None: minimum miktar filtresini biz yapiyoruz (birim donusumu icin)
        candidates = []
        for s in self._get_filtered_sellers(quantity=None, date=date):
            cost = self._anaroma_seller_cost_per_kg(s, date)
            if cost is False:
                continue
            min_kg = s.min_qty * self._anaroma_kg_per_uom(s.product_uom_id)
            candidates.append((s, cost, min_kg))

        if candidates:
            eligible = [c for c in candidates if c[2] <= qty_kg + 1e-9]
            if eligible:
                if method == "preferred":
                    # Odoo siralamasi: sira, buyuk minimum miktar once (daha iyi kademe)
                    top_seq = eligible[0][0].sequence
                    eligible = [c for c in eligible if c[0].sequence == top_seq]
                best = min(eligible, key=lambda c: (c[1], c[0].sequence, c[0].id))
            else:
                # Hicbir kademeye yetmiyor: en dusuk minimum miktarli fiyat
                best = min(candidates, key=lambda c: (c[2], c[1]))
                res["warning"] = "Minimum alım miktarının altında"
            res.update(cost=best[1], seller=best[0], source="seller")
            return res

        visited = set(_visited or ())
        formula = self.product_tmpl_id.anaroma_current_formula_id
        if formula and self.product_tmpl_id.id not in visited:
            visited.add(self.product_tmpl_id.id)
            res.update(cost=formula._anaroma_cost_per_kg(_visited=visited), source="formula")
            return res

        kg_per_uom = self._anaroma_kg_per_uom(self.uom_id)
        if self.standard_price and kg_per_uom:
            res.update(cost=self.standard_price / kg_per_uom, source="standard")
            return res

        res["warning"] = "Fiyat bulunamadı (tedarikçi fiyatı girin)"
        return res
