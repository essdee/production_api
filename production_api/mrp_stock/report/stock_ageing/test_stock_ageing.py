from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe

from production_api.mrp_stock.report.stock_ageing import stock_ageing


class TestStockAgeing(TestCase):
	def test_stock_older_than_last_range_is_returned_for_the_fourth_ageing_column(self):
		filters = frappe._dict(
			range1=30,
			range2=60,
			range3=90,
			show_warehouse_wise_stock=0,
		)
		item_details = {
			"Mens Sports Vest - 11225-85 cm": {
				"details": frappe._dict(
					name="Mens Sports Vest - 11225-85 cm",
					item_name="Mens Sports Vest - 11225",
					item_group="Products",
					brand=None,
					stock_uom="Pieces",
				),
				"fifo_queue": [[2360, "2024-12-19"]],
				"total_qty": 2360,
			}
		}

		frappe_context = SimpleNamespace(
			db=SimpleNamespace(get_single_value=lambda *args, **kwargs: 3)
		)
		with (
			patch.object(stock_ageing, "frappe", frappe_context),
			patch.object(
				stock_ageing,
				"flt",
				lambda value, precision=None: round(float(value), precision)
				if precision is not None
				else float(value),
			),
		):
			row = stock_ageing.format_report_data(filters, item_details, "2026-10-07")[0]

		self.assertEqual(row.get("range4"), 2360)
