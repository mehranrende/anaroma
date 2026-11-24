from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

COST_SOURCES = [
    ("seller", "Tedarikçi fiyatı"),
    ("formula", "Alt formül"),
    ("standard", "Ürün maliyeti"),
    ("none", "Fiyat yok"),
]


class AnaromaFormula(models.Model):
    _name = "anaroma.formula"
    _description = "Aroma / Esans Formülü"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "product_tmpl_id, version desc, id desc"
    _rec_names_search = ["name", "code", "product_tmpl_id"]

    code = fields.Char("Formül No", readonly=True, copy=False, default="Yeni", index="trigram")
    name = fields.Char("Formül Adı", required=True, tracking=True)
    product_tmpl_id = fields.Many2one(
        "product.template", string="Ürün", required=True, index=True, tracking=True,
        domain=[("anaroma_kind", "in", ("aroma", "essence"))], ondelete="restrict")
    product_kind = fields.Selection(related="product_tmpl_id.anaroma_kind", string="Tür")
    version = fields.Integer("Versiyon", default=1, readonly=True, copy=False)
    previous_formula_id = fields.Many2one("anaroma.formula", "Önceki Versiyon", readonly=True, copy=False)
    state = fields.Selection(
        [("draft", "Taslak"), ("approved", "Onaylı"), ("obsolete", "Eski")],
        default="draft", required=True, readonly=True, copy=False, tracking=True, string="Durum")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")

    line_ids = fields.One2many("anaroma.formula.line", "formula_id", string="Hammaddeler", copy=True)
    batch_size = fields.Float(
        "Parti Büyüklüğü (kg)", default=1.0, required=True, digits="Product Unit", tracking=True,
        help="Bir üretimde yapılan miktar. Hammadde ihtiyacı ve tedarikçi fiyat kademesi "
             "(minimum miktar) bu miktara göre seçilir; üretim reçetesi de bu miktarla oluşturulur.")
    cost_method = fields.Selection(
        [("cheapest", "En ucuz tedarikçi"), ("preferred", "Öncelikli tedarikçi")],
        string="Maliyet Yöntemi", default="cheapest", required=True,
        help="En ucuz: Minimum miktarı karşılayan tedarikçiler arasından en düşük kg fiyatı.\n"
             "Öncelikli: Ürünün tedarikçi listesindeki ilk sıradaki tedarikçi.")
    total_weight = fields.Float("Toplam Ağırlık (g)", compute="_compute_total_weight", store=True, digits=(16, 3))
    total_percentage = fields.Float("Toplam %", compute="_compute_total_weight", store=True, digits=(16, 3))

    cost_total = fields.Monetary("Formül Maliyeti", compute="_compute_costs",
                                 help="Formülde yazan toplam ağırlığın maliyeti.")
    cost_per_kg = fields.Monetary("Kg Maliyeti", compute="_compute_costs")
    batch_cost = fields.Monetary("Parti Maliyeti", compute="_compute_costs")
    cost_warning = fields.Boolean(compute="_compute_costs")

    approved_date = fields.Datetime("Onay Tarihi", readonly=True, copy=False)
    approved_by_id = fields.Many2one("res.users", "Onaylayan", readonly=True, copy=False)
    bom_id = fields.Many2one("mrp.bom", "Üretim Reçetesi", readonly=True, copy=False)
    notes = fields.Html("Notlar")

    _version_unique = models.Constraint(
        "UNIQUE(product_tmpl_id, version)", "Bu ürünün aynı versiyonda iki formülü olamaz.")
    _batch_size_positive = models.Constraint(
        "CHECK(batch_size > 0)", "Parti büyüklüğü sıfırdan büyük olmalı.")

    @api.depends("line_ids.weight")
    def _compute_total_weight(self):
        for formula in self:
            formula.total_weight = sum(formula.line_ids.mapped("weight"))
            formula.total_percentage = 100.0 if formula.total_weight else 0.0

    @api.depends("line_ids.line_cost", "line_ids.warning", "total_weight", "batch_size")
    def _compute_costs(self):
        for formula in self:
            formula.cost_total = sum(formula.line_ids.mapped("line_cost"))
            formula.cost_per_kg = formula.cost_total / (formula.total_weight / 1000.0) if formula.total_weight else 0.0
            formula.batch_cost = formula.cost_per_kg * formula.batch_size
            formula.cost_warning = any(formula.line_ids.mapped("warning"))

    def _compute_display_name(self):
        for formula in self:
            formula.display_name = f"{formula.code} - {formula.name} (v{formula.version})"

    def _anaroma_cost_per_kg(self, _visited=None):
        """Alt formul olarak kullanildiginda kg maliyeti (dongu korumali)."""
        self.ensure_one()
        total = sum(line._get_cost_info(_visited=_visited)["cost"] * line.weight / 1000.0 for line in self.line_ids)
        return total / (self.total_weight / 1000.0) if self.total_weight else 0.0

    @api.onchange("product_tmpl_id")
    def _onchange_product_tmpl_id(self):
        if self.product_tmpl_id and not self.name:
            self.name = self.product_tmpl_id.name

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "Yeni") == "Yeni":
                vals["code"] = self.env["ir.sequence"].next_by_code("anaroma.formula") or "Yeni"
            if vals.get("product_tmpl_id") and not vals.get("version"):
                last = self.search([("product_tmpl_id", "=", vals["product_tmpl_id"])], order="version desc", limit=1)
                vals["version"] = last.version + 1 if last else 1
        return super().create(vals_list)

    def write(self, vals):
        locked = {"line_ids", "product_tmpl_id", "batch_size"}
        if locked & set(vals) and self.filtered(lambda f: f.state != "draft"):
            raise UserError("Onaylı veya eski formül değiştirilemez. Değişiklik için yeni versiyon oluşturun.")
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        if self.filtered(lambda f: f.state != "draft"):
            raise UserError("Sadece taslak formüller silinebilir. Onaylı formülleri arşivlemek yerine yeni versiyon oluşturun.")

    # ------------------------------------------------------------------
    # Is akisi
    # ------------------------------------------------------------------
    def action_approve(self):
        for formula in self:
            if formula.state != "draft":
                continue
            if not formula.line_ids:
                raise UserError("Hammaddesi olmayan formül onaylanamaz.")
            older = self.search([
                ("product_tmpl_id", "=", formula.product_tmpl_id.id),
                ("state", "=", "approved"), ("id", "!=", formula.id)])
            older.write({"state": "obsolete"})
            older.bom_id.sudo().write({"active": False})
            formula.write({
                "state": "approved",
                "approved_date": fields.Datetime.now(),
                "approved_by_id": self.env.user.id,
            })
            formula._sync_bom()
        return True

    def action_set_draft(self):
        for formula in self.filtered(lambda f: f.state == "approved"):
            if formula.bom_id:
                formula.bom_id.sudo().write({"active": False})
            formula.state = "draft"
        return True

    def action_new_version(self):
        self.ensure_one()
        new = self.copy({"previous_formula_id": self.id, "name": self.name})
        return {
            "type": "ir.actions.act_window",
            "res_model": "anaroma.formula",
            "res_id": new.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_update_product_cost(self):
        """Urun kartindaki maliyet fiyatini formul maliyetiyle gunceller."""
        for formula in self:
            product = formula.product_tmpl_id.product_variant_id
            kg_per_uom = product._anaroma_kg_per_uom(product.uom_id)
            if not kg_per_uom:
                raise UserError(f"{product.display_name}: ürün birimi kg'a çevrilemiyor.")
            formula.product_tmpl_id.standard_price = formula.cost_per_kg * kg_per_uom
            formula.message_post(body=f"Ürün maliyeti güncellendi: {formula.cost_per_kg:.4f} {formula.currency_id.name}/kg")
        return True

    def action_view_bom(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.bom",
            "res_id": self.bom_id.id,
            "view_mode": "form",
            "context": {"active_test": False},
        }

    def _sync_bom(self):
        """Formulden MRP Uretim Recetesi olusturur/gunceller.
        Miktarlar urunlerin kendi biriminde (kg, L...) parti buyuklugune gore yazilir."""
        Bom = self.env["mrp.bom"].sudo()
        for formula in self:
            product = formula.product_tmpl_id.product_variant_id
            head_kg_per_uom = product._anaroma_kg_per_uom(product.uom_id)
            if not head_kg_per_uom:
                raise UserError(f"{product.display_name}: ürün birimi kg'a çevrilemiyor.")
            lines = []
            for line in formula.line_ids:
                comp = line.product_id
                kg_per_uom = comp._anaroma_kg_per_uom(comp.uom_id)
                if not kg_per_uom:
                    raise UserError(
                        f"{comp.display_name}: birimi kg'a çevrilemiyor. "
                        "Hacim birimi kullanılıyorsa hammaddeye yoğunluk girin.")
                lines.append({
                    "product_id": comp.id,
                    "product_qty": line.qty_kg / kg_per_uom,
                    "product_uom_id": comp.uom_id.id,
                    "sequence": line.sequence,
                })
            vals = {
                "product_tmpl_id": formula.product_tmpl_id.id,
                "product_qty": formula.batch_size / head_kg_per_uom,
                "product_uom_id": product.uom_id.id,
                "code": f"{formula.code} v{formula.version}",
                "type": "normal",
                "company_id": formula.company_id.id,
                "anaroma_formula_id": formula.id,
                "active": True,
                "sequence": 0,
            }
            if formula.bom_id:
                formula.bom_id.bom_line_ids.unlink()
                vals["bom_line_ids"] = [fields.Command.create(v) for v in lines]
                formula.bom_id.write(vals)
            else:
                vals["bom_line_ids"] = [fields.Command.create(v) for v in lines]
                formula.bom_id = Bom.create(vals)


class AnaromaFormulaLine(models.Model):
    _name = "anaroma.formula.line"
    _description = "Formül Satırı"
    _order = "formula_id, sequence, id"

    formula_id = fields.Many2one("anaroma.formula", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(related="formula_id.company_id", store=True)
    currency_id = fields.Many2one(related="formula_id.currency_id")
    product_id = fields.Many2one(
        "product.product", string="Hammadde", required=True, ondelete="restrict",
        domain=[("anaroma_kind", "!=", False)])
    product_tmpl_id = fields.Many2one(related="product_id.product_tmpl_id", store=True, index=True)
    cas_number = fields.Char(related="product_id.cas_number")
    weight = fields.Float("Ağırlık (g)", required=True, digits=(16, 3))
    percentage = fields.Float("%", compute="_compute_percentage", digits=(16, 3))
    qty_kg = fields.Float("Partide (kg)", compute="_compute_percentage", digits="Product Unit",
                          help="Parti büyüklüğüne göre gereken miktar.")
    supplierinfo_id = fields.Many2one(
        "product.supplierinfo", string="Sabit Tedarikçi",
        domain="[('product_tmpl_id', '=', product_tmpl_id)]",
        help="Boş bırakılırsa formülün maliyet yöntemine göre otomatik seçilir.")

    seller_id = fields.Many2one("product.supplierinfo", "Fiyat Kaynağı", compute="_compute_cost")
    partner_id = fields.Many2one("res.partner", "Tedarikçi", compute="_compute_cost")
    country_id = fields.Many2one("res.country", "Ülke", compute="_compute_cost")
    price_info = fields.Char("Tedarikçi Fiyatı", compute="_compute_cost")
    cost_source = fields.Selection(COST_SOURCES, "Kaynak", compute="_compute_cost")
    unit_cost = fields.Monetary("Kg Maliyeti", compute="_compute_cost")
    line_cost = fields.Monetary("Tutar", compute="_compute_cost")
    cost_share = fields.Float("Maliyet Payı %", compute="_compute_cost", digits=(16, 2))
    warning = fields.Char("Uyarı", compute="_compute_cost")

    _product_unique = models.Constraint(
        "UNIQUE(formula_id, product_id)", "Bir hammadde formülde yalnızca bir kez yer alabilir.")
    _weight_positive = models.Constraint("CHECK(weight > 0)", "Ağırlık sıfırdan büyük olmalı.")

    @api.constrains("product_id", "formula_id")
    def _check_not_self(self):
        for line in self:
            if line.product_tmpl_id == line.formula_id.product_tmpl_id:
                raise ValidationError("Bir ürün kendi formülünde hammadde olarak kullanılamaz.")

    def _check_formula_draft(self, formulas):
        if formulas.filtered(lambda f: f.state != "draft"):
            raise UserError("Onaylı veya eski formül değiştirilemez. Değişiklik için yeni versiyon oluşturun.")

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        self._check_formula_draft(lines.formula_id)
        return lines

    def write(self, vals):
        self._check_formula_draft(self.formula_id)
        res = super().write(vals)
        self._check_formula_draft(self.formula_id)
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        self._check_formula_draft(self.formula_id)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.supplierinfo_id and self.supplierinfo_id.product_tmpl_id != self.product_tmpl_id:
            self.supplierinfo_id = False

    @api.depends("weight", "formula_id.total_weight", "formula_id.batch_size")
    def _compute_percentage(self):
        for line in self:
            total = sum(line.formula_id.line_ids.mapped("weight"))
            line.percentage = line.weight / total * 100.0 if total else 0.0
            line.qty_kg = line.percentage / 100.0 * line.formula_id.batch_size

    def _get_cost_info(self, _visited=None):
        self.ensure_one()
        if not self.product_id:
            return {"cost": 0.0, "seller": self.env["product.supplierinfo"], "source": "none", "warning": False}
        visited = set(_visited or ())
        visited.add(self.formula_id.product_tmpl_id.id)
        return self.product_id._anaroma_cost_per_kg(
            qty_kg=self.qty_kg, seller=self.supplierinfo_id, method=self.formula_id.cost_method,
            _visited=visited)

    @api.depends("product_id", "weight", "qty_kg", "supplierinfo_id", "formula_id.cost_method",
                 "formula_id.batch_size", "formula_id.line_ids.weight")
    def _compute_cost(self):
        for formula in self.formula_id:
            lines = self.filtered(lambda l: l.formula_id == formula)
            total = 0.0
            for line in lines:
                info = line._get_cost_info()
                seller = info["seller"]
                line.seller_id = seller
                line.partner_id = seller.partner_id
                line.country_id = seller.partner_id.country_id
                line.price_info = (
                    f"{seller.price:,.4f} {seller.currency_id.name} / {seller.product_uom_id.name}"
                    + (f" (min {seller.min_qty:g} {seller.product_uom_id.name})" if seller.min_qty else "")
                ) if seller else False
                line.cost_source = info["source"]
                line.unit_cost = info["cost"]
                line.line_cost = info["cost"] * line.weight / 1000.0
                line.warning = info["warning"]
                total += line.line_cost
            for line in lines:
                line.cost_share = line.line_cost / total * 100.0 if total else 0.0
        for line in self.filtered(lambda l: not l.formula_id):
            line.update({
                "seller_id": False, "partner_id": False, "country_id": False, "price_info": False,
                "cost_source": "none", "unit_cost": 0.0, "line_cost": 0.0, "cost_share": 0.0, "warning": False,
            })
