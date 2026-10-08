import unittest

from production_api.production_api.page.supplier_pending_report import supplier_pending_report as report


class TestSupplierPendingReport(unittest.TestCase):
	def test_pending_boundary_is_strict_and_requires_delivered_quantity(self):
		self.assertTrue(report._row_is_pending(100, 90))
		self.assertFalse(report._row_is_pending(100, 90.01))
		self.assertFalse(report._row_is_pending(0, 0))
		self.assertFalse(report._row_is_pending(-1, 0))

	def test_builder_groups_sizes_and_work_orders_into_item_lot_colour_part_rows(self):
		work_orders = [
			{
				"name": "WO-1",
				"item": "ITEM-A",
				"lot": "LOT-1",
				"supplier_name": "Supplier A",
				"first_dc_date": "2026-01-01",
				"last_dc_date": "2026-01-02",
				"first_grn_date": "2026-01-03",
				"last_grn_date": "2026-01-05",
			},
			{
				"name": "WO-2",
				"item": "ITEM-A",
				"lot": "LOT-1",
				"supplier_name": "Supplier A",
				"first_dc_date": "2026-01-02",
				"last_dc_date": "2026-01-04",
				"first_grn_date": "2026-01-04",
				"last_grn_date": "2026-01-07",
			},
		]
		calculated_items = [
			{"parent": "WO-1", "item_variant": "NAVY-S", "set_combination": {"major_colour": "Navy"}, "delivered_quantity": 100, "received_qty": 40},
			{"parent": "WO-1", "item_variant": "NAVY-M", "set_combination": {"major_colour": "Navy"}, "delivered_quantity": 50, "received_qty": 10},
			{"parent": "WO-2", "item_variant": "NAVY-S", "set_combination": {"major_colour": "Navy"}, "delivered_quantity": 50, "received_qty": 20},
			{"parent": "WO-2", "item_variant": "NAVY-M", "set_combination": {"major_colour": "Navy"}, "delivered_quantity": 50, "received_qty": 10},
		]

		items = report._build_supplier_pending_items(
			work_orders,
			calculated_items,
			{"LOT-1": self._lot_context(is_set_item=True, primary_values=["S", "M"])},
			{
				"NAVY-S": {"Colour": "Navy", "Size": "S", "Part": "Top"},
				"NAVY-M": {"Colour": "Navy", "Size": "M", "Part": "Top"},
			},
			{"Supplier A": {"Navy": {"S": "Pass", "M": "Fail"}}},
		)

		self.assertEqual([item["item"] for item in items], ["ITEM-A"])
		lot = items[0]["lots"][0]
		self.assertEqual(lot["lot"], "LOT-1")
		self.assertEqual(lot["primary_values"], ["S", "M"])
		self.assertTrue(lot["is_set_item"])
		self.assertEqual(lot["set_attr"], "Part")
		self.assertEqual(len(lot["rows"]), 1)
		row = lot["rows"][0]
		self.assertEqual((row["colour"], row["part"]), ("Navy", "Top"))
		self.assertEqual(row["values"]["S"], {"delivered": 150.0, "received": 60.0, "difference": -90.0, "quality": "Pass"})
		self.assertEqual(row["values"]["M"], {"delivered": 100.0, "received": 20.0, "difference": -80.0, "quality": "Fail"})
		self.assertEqual(row["totals"], {"delivered": 250.0, "received": 80.0, "difference": -170.0})
		self.assertEqual(
			row["dates"],
			{
				"first_dc_date": "2026-01-01",
				"last_dc_date": "2026-01-04",
				"first_grn_date": "2026-01-03",
				"last_grn_date": "2026-01-07",
				"diff_days": 3,
			},
		)
		self.assertEqual(lot["totals"][0]["part"], "Top")
		self.assertEqual(lot["totals"][0]["totals"], row["totals"])

	def test_builder_filters_completed_rows_and_cascades_empty_lots_and_items(self):
		work_orders = [
			self._work_order("WO-KEEP", "ITEM-KEEP", "LOT-KEEP"),
			self._work_order("WO-HIDE", "ITEM-KEEP", "LOT-HIDE"),
			self._work_order("WO-ITEM-HIDE", "ITEM-HIDE", "LOT-ITEM-HIDE"),
		]
		calculated_items = [
			self._calculated_item("WO-KEEP", "KEEP-S", 100, 90, "Keep"),
			self._calculated_item("WO-KEEP", "HIDDEN-S", 100, 90.01, "Hidden"),
			self._calculated_item("WO-KEEP", "ZERO-S", 0, 0, "Zero"),
			self._calculated_item("WO-HIDE", "LOT-HIDDEN-S", 100, 91, "Lot Hidden"),
			self._calculated_item("WO-ITEM-HIDE", "ITEM-HIDDEN-S", 100, 100, "Item Hidden"),
		]
		lot_contexts = {
			lot: self._lot_context(is_set_item=False, primary_values=["S"])
			for lot in ("LOT-KEEP", "LOT-HIDE", "LOT-ITEM-HIDE")
		}
		variant_attributes = {
			variant: {"Colour": colour, "Size": "S"}
			for variant, colour in (
				("KEEP-S", "Keep"),
				("HIDDEN-S", "Hidden"),
				("ZERO-S", "Zero"),
				("LOT-HIDDEN-S", "Lot Hidden"),
				("ITEM-HIDDEN-S", "Item Hidden"),
			)
		}

		items = report._build_supplier_pending_items(work_orders, calculated_items, lot_contexts, variant_attributes, {})

		self.assertEqual(len(items), 1)
		self.assertEqual(items[0]["item"], "ITEM-KEEP")
		self.assertEqual([lot["lot"] for lot in items[0]["lots"]], ["LOT-KEEP"])
		self.assertEqual([(row["colour"], row["totals"]["received"]) for row in items[0]["lots"][0]["rows"]], [("Keep", 90.0)])

	def test_builder_supports_non_set_items_and_missing_dates(self):
		items = report._build_supplier_pending_items(
			[self._work_order("WO-1", "ITEM-A", "LOT-1")],
			[self._calculated_item("WO-1", "BLACK-S", 10, 4, "Black")],
			{"LOT-1": self._lot_context(is_set_item=False, primary_values=["S"])},
			{"BLACK-S": {"Colour": "Black", "Size": "S"}},
			{},
		)

		lot = items[0]["lots"][0]
		row = lot["rows"][0]
		self.assertFalse(lot["is_set_item"])
		self.assertIsNone(row["part"])
		self.assertEqual(row["dates"], {"first_dc_date": None, "last_dc_date": None, "first_grn_date": None, "last_grn_date": None, "diff_days": None})

	def test_builder_aggregates_multiple_work_orders_without_duplicate_rows(self):
		work_orders = [
			self._work_order("WO-1", "ITEM-A", "LOT-1"),
			self._work_order("WO-2", "ITEM-A", "LOT-1"),
		]
		items = report._build_supplier_pending_items(
			work_orders,
			[
				self._calculated_item("WO-1", "BLACK-S", 10, 2, "Black"),
				self._calculated_item("WO-2", "BLACK-S", 20, 3, "Black"),
			],
			{"LOT-1": self._lot_context(is_set_item=False, primary_values=["S"])},
			{"BLACK-S": {"Colour": "Black", "Size": "S"}},
			{},
		)

		rows = items[0]["lots"][0]["rows"]
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["values"]["S"]["delivered"], 30.0)
		self.assertEqual(rows[0]["values"]["S"]["received"], 5.0)

	@staticmethod
	def _lot_context(is_set_item, primary_values):
		return {
			"is_set_item": is_set_item,
			"packing_attribute": "Colour",
			"primary_item_attribute": "Size",
			"set_item_attribute": "Part",
			"major_attribute_value": "Top",
			"primary_values": primary_values,
		}

	@staticmethod
	def _work_order(name, item, lot):
		return {
			"name": name,
			"item": item,
			"lot": lot,
			"supplier_name": "Supplier A",
			"first_dc_date": None,
			"last_dc_date": None,
			"first_grn_date": None,
			"last_grn_date": None,
		}

	@staticmethod
	def _calculated_item(parent, variant, delivered, received, colour):
		return {
			"parent": parent,
			"item_variant": variant,
			"set_combination": {"major_colour": colour},
			"delivered_quantity": delivered,
			"received_qty": received,
		}
