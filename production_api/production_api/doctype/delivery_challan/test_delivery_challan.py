# Copyright (c) 2024, Essdee and Contributors
# See license.txt

from types import SimpleNamespace
from unittest import TestCase

from production_api.production_api.doctype.delivery_challan.delivery_challan import (
	DeliveryChallan,
	get_completed_garment_qty,
)


class TestDeliveryChallan(TestCase):
	def test_completed_garment_qty_uses_required_panel_quantity(self):
		self.assertEqual(get_completed_garment_qty(580, 2), 290)
		self.assertEqual(get_completed_garment_qty(464, 2), 232)
		self.assertEqual(get_completed_garment_qty(581, 2), 290)

	def test_completed_garment_qty_defaults_to_one_panel(self):
		self.assertEqual(get_completed_garment_qty(300, 0), 300)

	def test_sle_uses_rate_resolved_from_exact_source_stock(self):
		doc = SimpleNamespace(
			posting_date="2026-08-13",
			posting_time="10:00:00",
			doctype="Delivery Challan",
			name="DC-TEST",
			docstatus=1,
		)
		row = SimpleNamespace(
			item_variant="VARIANT-1",
			lot="LOT-1",
			uom="Nos",
			name="DC-ROW-1",
			stock_qty=3,
			rate=303.226,
			precision=lambda _field: 9,
		)

		sle = DeliveryChallan.get_sle_data(
			doc, row, "TARGET-WAREHOUSE", 1, {}, "Accepted"
		)

		self.assertEqual(sle.rate, 303.226)
		self.assertEqual(sle.valuation_rate, 303.226)
		self.assertEqual(sle.warehouse, "TARGET-WAREHOUSE")

	def test_cancel_sle_leaves_rate_empty_for_original_sle_rate_lookup(self):
		doc = SimpleNamespace(
			posting_date="2026-08-13",
			posting_time="10:00:00",
			doctype="Delivery Challan",
			name="DC-TEST",
			docstatus=2,
		)
		row = SimpleNamespace(
			item_variant="VARIANT-1",
			lot="LOT-1",
			uom="Nos",
			name="DC-ROW-1",
			stock_qty=3,
			rate=303.226,
			precision=lambda _field: 9,
		)

		sle = DeliveryChallan.get_sle_data(
			doc, row, "SOURCE-WAREHOUSE", -1, {}, "Accepted"
		)

		self.assertEqual(sle.rate, 0)
		self.assertEqual(sle.valuation_rate, 0)
		self.assertEqual(sle.is_cancelled, 1)
