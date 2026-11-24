from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestAnaromaFormula(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env.company
        cls.cur = cls.company.currency_id
        cls.foreign = env.ref("base.EUR") if cls.cur != env.ref("base.EUR") else env.ref("base.USD")
        cls.foreign.active = True
        # 1 doviz = 2 sirket para birimi
        env["res.currency.rate"].search([("currency_id", "=", cls.foreign.id)]).unlink()
        env["res.currency.rate"].create({
            "currency_id": cls.foreign.id, "rate": 0.5,
            "name": fields.Date.today(), "company_id": cls.company.id,
        })
        cls.kg = env.ref("uom.product_uom_kgm")
        cls.g = env.ref("uom.product_uom_gram")
        cls.litre = env.ref("uom.product_uom_litre")
        cls.drum = env.ref("anaroma_formula.uom_drum_25kg")

        Partner = env["res.partner"]
        cls.vendor_fr = Partner.create({"name": "Grasse SA", "country_id": env.ref("base.fr").id})
        cls.vendor_in = Partner.create({"name": "Mumbai Oils", "country_id": env.ref("base.in").id})
        cls.vendor_tr = Partner.create({"name": "Isparta Gül", "country_id": env.ref("base.tr").id})

        Product = env["product.template"]
        cls.raw_a = Product.create({"name": "Linalool", "anaroma_kind": "raw", "cas_number": "78-70-6"})
        cls.raw_b = Product.create({"name": "Vanilin", "anaroma_kind": "raw"})
        cls.raw_c = Product.create({"name": "Gül Yağı", "anaroma_kind": "raw",
                                    "anaroma_density": 0.8, "uom_id": cls.litre.id})
        Seller = env["product.supplierinfo"]
        # Linalool: Fransa 10/kg min 0; Hindistan 4 EUR(=8)/kg min 50 kg
        cls.s_a_fr = Seller.create({"product_tmpl_id": cls.raw_a.id, "partner_id": cls.vendor_fr.id,
                                    "price": 10, "currency_id": cls.cur.id, "product_uom_id": cls.kg.id,
                                    "sequence": 1})
        cls.s_a_in = Seller.create({"product_tmpl_id": cls.raw_a.id, "partner_id": cls.vendor_in.id,
                                    "price": 4, "currency_id": cls.foreign.id, "product_uom_id": cls.kg.id,
                                    "min_qty": 50, "sequence": 2})
        # Vanilin: gram fiyatli 0.02/g = 20/kg
        Seller.create({"product_tmpl_id": cls.raw_b.id, "partner_id": cls.vendor_fr.id,
                       "price": 0.02, "currency_id": cls.cur.id, "product_uom_id": cls.g.id})
        # Gul yagi: litre fiyatli 16/L, yogunluk 0.8 => 20/kg
        Seller.create({"product_tmpl_id": cls.raw_c.id, "partner_id": cls.vendor_tr.id,
                       "price": 16, "currency_id": cls.cur.id, "product_uom_id": cls.litre.id})

        cls.essence = Product.create({"name": "Vanilya Esansı", "anaroma_kind": "essence"})
        cls.formula = env["anaroma.formula"].create({
            "name": "Vanilya", "product_tmpl_id": cls.essence.id, "batch_size": 10,
            "line_ids": [
                fields.Command.create({"product_id": cls.raw_a.product_variant_id.id, "weight": 600}),
                fields.Command.create({"product_id": cls.raw_b.product_variant_id.id, "weight": 400}),
            ],
        })

    def test_product_defaults(self):
        self.assertEqual(self.raw_a.uom_id, self.kg)
        self.assertTrue(self.raw_a.is_storable)
        self.assertFalse(self.raw_a.sale_ok)
        self.assertTrue(self.raw_a.purchase_ok)
        self.assertTrue(self.essence.sale_ok)

    def test_percentages(self):
        f = self.formula
        self.assertEqual(f.total_weight, 1000)
        self.assertEqual(f.line_ids.mapped("percentage"), [60, 40])
        self.assertEqual(f.line_ids.mapped("qty_kg"), [6, 4])
        self.assertTrue(f.code.startswith("FRM-"))
        self.assertEqual(f.version, 1)

    def test_supplier_price_per_kg(self):
        self.assertAlmostEqual(self.s_a_in.anaroma_price_per_kg, 8.0)    # 4 EUR x 2
        self.assertAlmostEqual(self.raw_b.seller_ids.anaroma_price_per_kg, 20.0)  # gram -> kg
        self.assertAlmostEqual(self.raw_c.seller_ids.anaroma_price_per_kg, 20.0)  # litre + yogunluk
        self.assertAlmostEqual(self.raw_c.seller_ids.anaroma_min_qty_kg, 0.0)
        self.assertEqual(self.s_a_in.anaroma_country_id, self.env.ref("base.in"))

    def test_cost_small_batch_uses_tier_without_minimum(self):
        f = self.formula  # 10 kg parti => 6 kg linalool < 50 kg minimum
        line_a = f.line_ids[0]
        self.assertEqual(line_a.seller_id, self.s_a_fr)
        self.assertAlmostEqual(line_a.unit_cost, 10.0)
        self.assertAlmostEqual(f.cost_per_kg, 0.6 * 10 + 0.4 * 20)
        self.assertAlmostEqual(f.batch_cost, 14.0 * 10)
        self.assertFalse(f.cost_warning)

    def test_cost_large_batch_uses_cheaper_tier_and_currency(self):
        f = self.formula
        f.batch_size = 100  # 60 kg linalool >= 50 kg => Hindistan 8/kg
        line_a = f.line_ids[0]
        self.assertEqual(line_a.seller_id, self.s_a_in)
        self.assertEqual(line_a.country_id, self.env.ref("base.in"))
        self.assertAlmostEqual(f.cost_per_kg, 0.6 * 8 + 0.4 * 20)

    def test_preferred_method(self):
        f = self.formula
        f.write({"batch_size": 100, "cost_method": "preferred"})
        self.assertEqual(f.line_ids[0].seller_id, self.s_a_fr)  # sira 1
        self.assertAlmostEqual(f.cost_per_kg, 14.0)

    def test_fixed_supplier_below_minimum_warns(self):
        line_a = self.formula.line_ids[0]
        line_a.supplierinfo_id = self.s_a_in
        self.assertAlmostEqual(line_a.unit_cost, 8.0)
        self.assertTrue(line_a.warning)
        self.assertTrue(self.formula.cost_warning)

    def test_packaging_unit(self):
        self.s_a_fr.write({"product_uom_id": self.drum.id, "price": 200})  # 200 / 25 kg
        self.assertAlmostEqual(self.s_a_fr.anaroma_price_per_kg, 8.0)

    def test_volume_without_density_is_flagged(self):
        self.raw_c.anaroma_density = 0
        self.formula.line_ids = [fields.Command.create({"product_id": self.raw_c.product_variant_id.id, "weight": 100})]
        line_c = self.formula.line_ids.filtered(lambda l: l.product_tmpl_id == self.raw_c)
        self.assertEqual(line_c.cost_source, "none")
        self.assertTrue(line_c.warning)

    def test_approve_creates_bom_and_locks(self):
        f = self.formula
        f.action_approve()
        self.assertEqual(f.state, "approved")
        bom = f.bom_id
        self.assertTrue(bom)
        self.assertEqual(bom.product_tmpl_id, self.essence)
        self.assertAlmostEqual(bom.product_qty, 10)
        self.assertEqual(bom.bom_line_ids.mapped("product_qty"), [6, 4])
        self.assertEqual(bom.anaroma_formula_id, f)
        with self.assertRaises(UserError):
            f.line_ids[0].weight = 1
        with self.assertRaises(UserError):
            f.batch_size = 5

    def test_bom_volume_component_in_litres(self):
        self.formula.line_ids = [fields.Command.create({"product_id": self.raw_c.product_variant_id.id, "weight": 1000})]
        self.formula.action_approve()
        bom_line = self.formula.bom_id.bom_line_ids.filtered(lambda l: l.product_tmpl_id == self.raw_c)
        # 2000 g formulde 1000 g gul yagi => 10 kg partide 5 kg = 6.25 L
        self.assertEqual(bom_line.product_uom_id, self.litre)
        self.assertAlmostEqual(bom_line.product_qty, 6.25)

    def test_new_version(self):
        f1 = self.formula
        f1.action_approve()
        action = f1.action_new_version()
        f2 = self.env["anaroma.formula"].browse(action["res_id"])
        self.assertEqual((f2.version, f2.state, f2.previous_formula_id), (2, "draft", f1))
        self.assertEqual(len(f2.line_ids), 2)
        self.assertNotEqual(f2.code, f1.code)
        f2.line_ids[0].weight = 500
        f2.action_approve()
        self.assertEqual(f1.state, "obsolete")
        self.assertFalse(f1.bom_id.active)
        self.assertTrue(f2.bom_id.active)
        self.assertEqual(self.essence.anaroma_current_formula_id, f2)
        self.assertEqual(self.essence.anaroma_formula_count, 2)
        self.assertEqual(self.raw_a.anaroma_used_in_count, 2)

    def test_update_product_cost(self):
        self.formula.action_approve()
        self.formula.action_update_product_cost()
        self.assertAlmostEqual(self.essence.standard_price, 14.0)

    def test_sub_formula_cost(self):
        self.formula.action_approve()
        perfume = self.env["product.template"].create({"name": "Parfüm Bazı", "anaroma_kind": "aroma"})
        f = self.env["anaroma.formula"].create({
            "name": "Baz", "product_tmpl_id": perfume.id,
            "line_ids": [
                fields.Command.create({"product_id": self.essence.product_variant_id.id, "weight": 500}),
                fields.Command.create({"product_id": self.raw_b.product_variant_id.id, "weight": 500}),
            ],
        })
        line_e = f.line_ids[0]
        self.assertEqual(line_e.cost_source, "formula")
        self.assertAlmostEqual(line_e.unit_cost, 14.0)
        self.assertAlmostEqual(f.cost_per_kg, 17.0)

    def test_constraints(self):
        with self.assertRaises(ValidationError):
            self.formula.line_ids = [fields.Command.create({
                "product_id": self.essence.product_variant_id.id, "weight": 1})]
        with mute_logger("odoo.sql_db"), self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.formula.line_ids = [fields.Command.create({
                    "product_id": self.raw_a.product_variant_id.id, "weight": 1})]
        self.formula.action_approve()
        with self.assertRaises(UserError):
            self.formula.unlink()

    def test_access_rights(self):
        user = self.env["res.users"].create({
            "name": "Depo", "login": "depo_test", "group_ids": [fields.Command.set([self.env.ref("base.group_user").id])]})
        with self.assertRaises(Exception):
            self.formula.with_user(user).read(["name"])
        user.group_ids = [fields.Command.link(self.env.ref("anaroma_formula.group_formula_user").id)]
        self.assertEqual(self.formula.with_user(user).name, "Vanilya")
        with self.assertRaises(Exception):
            self.formula.with_user(user).name = "X"
