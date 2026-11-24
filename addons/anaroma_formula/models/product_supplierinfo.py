from odoo import api, fields, models


class ProductSupplierinfo(models.Model):
    _inherit = "product.supplierinfo"

    # Farkli birim ve para birimlerindeki degerlerin toplami anlamsiz: grup toplamlarini kapat
    min_qty = fields.Float(aggregator=False)
    price = fields.Float(aggregator=False)
    delay = fields.Integer(aggregator=False)

    anaroma_country_id = fields.Many2one(
        related="partner_id.country_id", string="Ülke", readonly=True)
    anaroma_company_currency_id = fields.Many2one(
        "res.currency", compute="_compute_anaroma_price_per_kg")
    anaroma_min_qty_kg = fields.Float(
        "Min. Miktar (kg)", digits="Product Unit", compute="_compute_anaroma_price_per_kg")
    anaroma_price_per_kg = fields.Monetary(
        "Kg Fiyatı", currency_field="anaroma_company_currency_id",
        compute="_compute_anaroma_price_per_kg",
        help="İndirim, birim dönüşümü ve güncel döviz kuruyla şirket para biriminde kg fiyatı.")

    @api.depends("price", "discount", "currency_id", "product_uom_id", "min_qty",
                 "product_tmpl_id.anaroma_density", "company_id")
    @api.depends_context("company")
    def _compute_anaroma_price_per_kg(self):
        for rec in self:
            company = rec.company_id or self.env.company
            rec.anaroma_company_currency_id = company.currency_id
            product = rec.product_id or rec.product_tmpl_id.product_variant_id
            kg_per_uom = product._anaroma_kg_per_uom(rec.product_uom_id) if product else False
            if kg_per_uom:
                rec.anaroma_min_qty_kg = rec.min_qty * kg_per_uom
                rec.anaroma_price_per_kg = product._anaroma_seller_cost_per_kg(rec)
            else:
                rec.anaroma_min_qty_kg = 0.0
                rec.anaroma_price_per_kg = 0.0
