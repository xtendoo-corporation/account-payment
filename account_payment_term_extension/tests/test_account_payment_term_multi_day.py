import odoo.tests.common as common
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import Form


class TestAccountPaymentTermMultiDay(common.TransactionCase):
    def setUp(self):
        super(TestAccountPaymentTermMultiDay, self).setUp()
        self.payment_term_model = self.env["account.payment.term"]
        self.invoice_model = self.env["account.move"]
        self.partner = self.env["res.partner"].create({"name": "Test Partner"})
        self.product = self.env["product.product"].create({"name": "Test product"})
        self.payment_term_0_day_5 = self.payment_term_model.create(
            {
                "name": "Normal payment in day 5",
                "active": True,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "value": "balance",
                            "days": 5,
                            "payment_days": "5",
                            "day_of_the_month": 31,
                        },
                    )
                ],
            }
        )
        self.payment_term_0_days_5_10 = self.payment_term_model.create(
            {
                "name": "Payment for days 5 and 10",
                "active": True,
                "line_ids": [
                    (0, 0, {"value": "balance", "days": 0, "payment_days": "5,10"})
                ],
            }
        )
        self.payment_term_0_days_15_20_then_5_10 = self.payment_term_model.create(
            {
                "name": "Payment for days 15 and 20 then 5 and 10",
                "active": True,
                "sequential_lines": True,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "value": "percent",
                            "value_amount": 50.0,
                            "days": 0,
                            "payment_days": "15,20",
                            "option": "day_after_invoice_date",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "value": "balance",
                            "days": 0,
                            "payment_days": "10-5",
                            "option": "day_after_invoice_date",
                        },
                    ),
                ],
            }
        )
        self.payment_term_round = self.payment_term_model.create(
            {
                "name": "Payment for days 15 and 20 then 5 and 10 with round",
                "active": True,
                "sequential_lines": True,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "value": "percent",
                            "value_amount": 50.0,
                            "amount_round": 1,
                            "days": 10,
                            "payment_days": "15,20",
                            "option": "day_following_month",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "value": "balance",
                            "days": 10,
                            "payment_days": "10-5",
                            "option": "day_following_month",
                        },
                    ),
                ],
            }
        )
        self.amount_untaxed_lines = self.payment_term_model.create(
            {
                "name": "10 percent + 40 percent + Balance",
                "active": True,
                "sequential_lines": True,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "value": "percent_amount_untaxed",
                            "value_amount": 10.0,
                            "option": "day_after_invoice_date",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "value": "percent_amount_untaxed",
                            "value_amount": 40.0,
                            "option": "day_after_invoice_date",
                        },
                    ),
                    (0, 0, {"value": "balance", "option": "day_after_invoice_date"}),
                ],
            }
        )

    def _create_invoice(self, payment_term, date, quantity, price_unit):
        invoice_form = Form(self.invoice_model.with_context(default_type="in_invoice"))
        invoice_form.partner_id = self.partner
        invoice_form.invoice_payment_term_id = payment_term
        invoice_form.invoice_date = date
        with invoice_form.invoice_line_ids.new() as line_form:
            line_form.product_id = self.product
            line_form.quantity = quantity
            line_form.price_unit = price_unit
            line_form.tax_ids.clear()
        invoice = invoice_form.save()
        return invoice

    def test_amount_untaxed_payment_term_error(self):
        payment_term_form = Form(self.payment_term_model)
        payment_term_form.name = "10 percent + 40 percent + Balance"
        payment_term_form.sequential_lines = True
        with payment_term_form.line_ids.new() as line_form:
            line_form.value = "percent_amount_untaxed"
            line_form.value_amount = 110
            line_form.option = "day_after_invoice_date"
        with self.assertRaises(ValidationError):
            payment_term_form.save()

    def test_invoice_amount_untaxed_payment_term(self):
        invoice = self._create_invoice(self.amount_untaxed_lines, "2020-01-01", 10, 100)
        tax = self.env["account.tax"].create(
            {
                "name": "Test tax",
                "amount_type": "percent",
                "amount": 10,
                "type_tax_use": "purchase",
            }
        )
        with Form(invoice) as invoice_form:
            with invoice_form.invoice_line_ids.edit(0) as line_form:
                line_form.tax_ids.add(tax)
        invoice.post()
        self.assertEqual(invoice.line_ids[1].credit, 100.0)
        self.assertEqual(invoice.line_ids[2].credit, 400.0)
        self.assertEqual(invoice.line_ids[3].credit, 600.0)

    def test_invoice_normal_payment_term(self):
        invoice = self._create_invoice(self.payment_term_0_day_5, "2020-01-01", 10, 100)
        invoice.post()
        for line in invoice.line_ids:
            if line.date_maturity:
                self.assertEqual(
                    fields.Date.to_string(line.date_maturity),
                    "2020-02-05",
                    "Incorrect due date for invoice with normal payment day on 5",
                )

    def test_invoice_multi_payment_term_day_1(self):
        invoice = self._create_invoice(
            self.payment_term_0_days_5_10, "2020-01-01", 10, 100
        )
        invoice.post()
        for line in invoice.line_ids:
            if line.date_maturity:
                self.assertEqual(
                    fields.Date.to_string(line.date_maturity),
                    "2020-01-05",
                    "Incorrect due date for invoice with payment days on 5 and 10 (1)",
                )

    def test_invoice_multi_payment_term_day_6(self):
        invoice = self._create_invoice(
            self.payment_term_0_days_5_10, "2020-01-06", 10, 100
        )
        invoice.post()
        for line in invoice.line_ids:
            if line.date_maturity:
                self.assertEqual(
                    fields.Date.to_string(line.date_maturity),
                    "2020-01-10",
                    "Incorrect due date for invoice with payment days on 5 and 10 (2)",
                )

    def test_invoice_multi_payment_term_sequential_day_1(self):
        invoice = self._create_invoice(
            self.payment_term_0_days_15_20_then_5_10, "2020-01-01", 10, 100
        )
        invoice.post()
        dates_maturity = []
        for line in invoice.line_ids:
            if line.date_maturity:
                dates_maturity.append(line.date_maturity)
        dates_maturity.sort()
        self.assertEqual(
            fields.Date.to_string(dates_maturity[0]),
            "2020-01-15",
            "Incorrect due date for invoice with payment days on "
            "15 and 20 then 5 and 10 (1)",
        )
        self.assertEqual(
            fields.Date.to_string(dates_maturity[1]),
            "2020-02-05",
            "Incorrect due date for invoice with payment days on "
            "15 and 20 then 5 and 10 (1)",
        )

    def test_invoice_multi_payment_term_sequential_day_18(self):
        invoice = self._create_invoice(
            self.payment_term_0_days_15_20_then_5_10, "2020-01-18", 10, 100
        )
        invoice.post()
        dates_maturity = []
        for line in invoice.line_ids:
            if line.date_maturity:
                dates_maturity.append(line.date_maturity)
        dates_maturity.sort()
        self.assertEqual(
            fields.Date.to_string(dates_maturity[0]),
            "2020-01-20",
            "Incorrect due date for invoice with payment days on "
            "15 and 20 then 5 and 10 (2)",
        )
        self.assertEqual(
            fields.Date.to_string(dates_maturity[1]),
            "2020-02-05",
            "Incorrect due date for invoice with payment days on "
            "15 and 20 then 5 and 10 (2)",
        )

    def test_invoice_multi_payment_term_sequential_day_25(self):
        invoice = self._create_invoice(
            self.payment_term_0_days_15_20_then_5_10, "2020-01-25", 10, 100
        )
        invoice.post()
        dates_maturity = []
        for line in invoice.line_ids:
            if line.date_maturity:
                dates_maturity.append(line.date_maturity)
        dates_maturity.sort()
        self.assertEqual(
            fields.Date.to_string(dates_maturity[0]),
            "2020-02-15",
            "Incorrect due date for invoice with payment days on "
            "15 and 20 then 5 and 10 (3)",
        )
        self.assertEqual(
            fields.Date.to_string(dates_maturity[1]),
            "2020-03-05",
            "Incorrect due date for invoice with payment days on "
            "15 and 20 then 5 and 10 (3)",
        )

    def test_invoice_multi_payment_term_round(self):
        invoice = self._create_invoice(
            self.payment_term_round, "2020-01-25", 10, 100.01
        )
        invoice.post()
        amounts = []
        for line in invoice.line_ids:
            if line.date_maturity:
                amounts.append(line.credit)
        self.assertEqual(
            amounts[0],
            500,
            "Incorrect round for invoice with payment days on "
            "15 and 20 then 5 and 10 (round)",
        )

    def test_decode_payment_days(self):
        expected_days = [5, 10]
        model = self.env["account.payment.term.line"]
        self.assertEqual(expected_days, model._decode_payment_days("5,10"))
        self.assertEqual(expected_days, model._decode_payment_days("5-10"))
        self.assertEqual(expected_days, model._decode_payment_days("5 10"))
        self.assertEqual(expected_days, model._decode_payment_days("10,5"))
        self.assertEqual(expected_days, model._decode_payment_days("10-5"))
        self.assertEqual(expected_days, model._decode_payment_days("10 5"))
        self.assertEqual(expected_days, model._decode_payment_days("5, 10"))
        self.assertEqual(expected_days, model._decode_payment_days("5 - 10"))
        self.assertEqual(expected_days, model._decode_payment_days("5    10"))
