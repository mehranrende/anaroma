from odoo import fields, models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    anaroma_formula_id = fields.Many2one(
        "anaroma.formula", string="Anaroma Formülü", readonly=True, index="btree_not_null",
        ondelete="set null", copy=False)
