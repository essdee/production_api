# Copyright (c) 2023, Essdee and Contributors
# See license.txt

from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.purchase_invoice.purchase_invoice import (
	_calculate_verification_grand_total,
)


class TestPurchaseInvoice(FrappeTestCase):
	def test_verification_grand_total_reconciles_all_colours_and_sizes(self):
		data = {
			"sizes": ["S", "M"],
			"colours": {
				"Red": {
					"data": {
						"S": {
							"total_delivered": 100,
							"total_received": 90,
							"billed": 80,
							"quantity": 15,
						},
						"M": {
							"total_delivered": 50,
							"total_received": 60,
							"billed": 40,
							"quantity": 20,
						},
					},
				},
				"Blue": {
					"data": {
						"S": {
							"total_delivered": 25,
							"total_received": 30,
							"billed": 20,
							"quantity": 5,
						},
						"M": {
							"total_delivered": 40,
							"total_received": 35,
							"billed": 30,
							"quantity": 10,
						},
					},
				},
			},
		}

		grand_total = _calculate_verification_grand_total(data)

		self.assertEqual(
			grand_total["sizes"]["S"],
			{
				"total_delivered": 125,
				"total_received": 120,
				"difference": 5,
				"total_billed": 100,
				"pending_for_bill": 20,
				"grn_quantity": 20,
			},
		)
		self.assertEqual(
			grand_total["sizes"]["M"],
			{
				"total_delivered": 90,
				"total_received": 95,
				"difference": -5,
				"total_billed": 70,
				"pending_for_bill": 25,
				"grn_quantity": 30,
			},
		)
		self.assertEqual(
			grand_total["total"],
			{
				"total_delivered": 215,
				"total_received": 215,
				"difference": 0,
				"total_billed": 170,
				"pending_for_bill": 45,
				"grn_quantity": 50,
			},
		)
