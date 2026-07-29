# Copyright (c) 2024, Essdee and Contributors
# See license.txt

from unittest import TestCase

from production_api.production_api.doctype.delivery_challan.delivery_challan import (
	get_completed_garment_qty,
)


class TestDeliveryChallan(TestCase):
	def test_completed_garment_qty_uses_required_panel_quantity(self):
		self.assertEqual(get_completed_garment_qty(580, 2), 290)
		self.assertEqual(get_completed_garment_qty(464, 2), 232)
		self.assertEqual(get_completed_garment_qty(581, 2), 290)

	def test_completed_garment_qty_defaults_to_one_panel(self):
		self.assertEqual(get_completed_garment_qty(300, 0), 300)
