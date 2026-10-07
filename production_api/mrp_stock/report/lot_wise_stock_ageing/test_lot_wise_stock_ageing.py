from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from production_api.mrp_stock.report.lot_wise_stock_ageing import lot_wise_stock_ageing


class TestLotWiseStockAgeing(TestCase):
	def test_stock_older_than_last_range_is_returned_for_the_fourth_ageing_column(self):
		filters = frappe._dict(
			range1=30,
			range2=60,
			range3=90,
			show_warehouse_wise_stock=0,
		)
		item_details = {
			("Mens Sports Vest - 11225-85 cm", "LOT-001"): {
				"details": frappe._dict(
					name="Mens Sports Vest - 11225-85 cm",
					item_name="Mens Sports Vest - 11225",
					item_group="Products",
					brand=None,
					lot="LOT-001",
					stock_uom="Pieces",
				),
				"fifo_queue": [[2360, "2024-12-19", 25]],
				"total_qty": 2360,
			}
		}

		frappe_context = SimpleNamespace(
			db=SimpleNamespace(get_single_value=lambda *args, **kwargs: 3)
		)
		with (
			patch.object(lot_wise_stock_ageing, "frappe", frappe_context),
			patch.object(
				lot_wise_stock_ageing,
				"flt",
				lambda value, precision=None: round(float(value), precision)
				if precision is not None
				else float(value),
			),
		):
			row = lot_wise_stock_ageing.format_report_data(
				filters, item_details, "2026-10-07"
			)[0]

		self.assertEqual(row.get("range4"), 2360)
