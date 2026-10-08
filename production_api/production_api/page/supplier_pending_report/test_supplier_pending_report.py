import json
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe

from production_api.production_api.page.supplier_pending_report import supplier_pending_report as report


class TestSupplierPendingReport(unittest.TestCase):
	def test_page_and_workspace_metadata_register_supplier_pending_report(self):
		page_directory = Path(__file__).resolve().parent
		page = json.loads((page_directory / "supplier_pending_report.json").read_text())
		workspace_path = page_directory.parents[2] / "essdee_production" / "workspace" / "manufacturing" / "manufacturing.json"
		workspace = json.loads(workspace_path.read_text())

		self.assertEqual(page["name"], "supplier-pending-report")
		self.assertEqual(page["page_name"], "supplier-pending-report")
		self.assertEqual(page["title"], "Supplier Pending Report")
		self.assertEqual(page["module"], "Production Api")
		self.assertEqual(page["standard"], "Yes")
		matching_links = [
			entry
			for entry in workspace["links"]
			if entry.get("label") == "Supplier Pending Report"
		]
		self.assertEqual(len(matching_links), 1)
		self.assertEqual(matching_links[0]["type"], "Link")
		self.assertEqual(matching_links[0]["link_type"], "Page")
		self.assertEqual(matching_links[0]["link_to"], "supplier-pending-report")

	def test_endpoint_requires_supplier(self):
		with (
			patch.object(report, "_", side_effect=lambda message: message),
			patch.object(report.frappe, "throw", side_effect=self._throw_validation),
			self.assertRaisesRegex(frappe.ValidationError, "Select a Supplier"),
		):
			report.get_supplier_pending_report.__wrapped__(None, "Cutting")

	def test_endpoint_requires_process(self):
		with (
			patch.object(report, "_", side_effect=lambda message: message),
			patch.object(report.frappe, "throw", side_effect=self._throw_validation),
			self.assertRaisesRegex(frappe.ValidationError, "Select a Process"),
		):
			report.get_supplier_pending_report.__wrapped__("SUP-001", None)

	def test_process_resolution_matches_existing_parent_group_semantics(self):
		with patch.object(report, "frappe") as frappe_mock:
			frappe_mock.db.sql.return_value = [
				{"parent": "Panel Cutting"},
				{"parent": "Cutting"},
				{"parent": "Cutting"},
			]
			process_names = report._resolve_process_names("Cutting")

		self.assertEqual(process_names, ("Cutting", "Panel Cutting"))
		self.assertEqual(frappe_mock.db.sql.call_args.kwargs["as_dict"], True)
		self.assertEqual(frappe_mock.db.sql.call_args.args[1], {"process": "Cutting"})

	def test_work_order_loader_filters_supplier_submitted_non_rework_and_processes(self):
		with patch.object(report, "frappe") as frappe_mock:
			frappe_mock.get_all.return_value = [{"name": "WO-1"}]
			rows = report._get_supplier_work_orders("SUP-001", ("Cutting", "Panel Cutting"))

		self.assertEqual(rows, [{"name": "WO-1"}])
		self.assertEqual(
			frappe_mock.get_all.call_args.kwargs["filters"],
			{
				"supplier": "SUP-001",
				"docstatus": 1,
				"is_rework": 0,
				"process_name": ["in", ("Cutting", "Panel Cutting")],
			},
		)
		self.assertEqual(
			frappe_mock.get_all.call_args.kwargs["fields"],
			[
				"name",
				"supplier",
				"supplier_name",
				"item",
				"lot",
				"process_name",
				"first_dc_date",
				"last_dc_date",
				"first_grn_date",
				"last_grn_date",
			],
		)

	def test_endpoint_returns_stable_empty_response_without_work_orders(self):
		with (
			patch.object(report, "_resolve_process_names", return_value=("Cutting",)),
			patch.object(report, "_get_supplier_work_orders", return_value=[]),
			patch.object(report, "frappe") as frappe_mock,
		):
			frappe_mock.get_cached_value.return_value = "Supplier A"
			result = report.get_supplier_pending_report.__wrapped__("SUP-001", "Cutting")

		self.assertEqual(
			result,
			{"supplier": "SUP-001", "supplier_name": "Supplier A", "process": "Cutting", "items": []},
		)

	def test_endpoint_does_not_load_quality_inspection_data(self):
		work_orders = [self._work_order("WO-1", "ITEM-A", "LOT-1")]
		work_orders[0]["supplier"] = "SUP-001"
		calculated_items = [self._calculated_item("WO-1", "BLACK-S", 10, 4, "Black")]
		lot_contexts = {"LOT-1": self._lot_context(False, ["S"])}
		variant_attributes = {"BLACK-S": {"Colour": "Black", "Size": "S"}}
		built_items = [{"item": "ITEM-A", "lots": []}]

		with (
			patch.object(report, "_resolve_process_names", return_value=("Cutting",)),
			patch.object(report, "_get_supplier_work_orders", return_value=work_orders),
			patch.object(report, "_load_lot_contexts", return_value=lot_contexts) as load_lots,
			patch.object(report, "_load_variant_attributes", return_value=variant_attributes) as load_variants,
			patch.object(
				report,
				"get_eqi_status",
				create=True,
				side_effect=AssertionError("Quality Inspection must not be queried"),
			),
			patch.object(report, "_build_supplier_pending_items", return_value=built_items) as builder,
			patch.object(report, "frappe") as frappe_mock,
		):
			frappe_mock.get_cached_value.return_value = "Supplier A"
			frappe_mock.get_all.return_value = calculated_items
			result = report.get_supplier_pending_report.__wrapped__("SUP-001", "Cutting")

		self.assertEqual(result["items"], built_items)
		self.assertEqual(frappe_mock.get_all.call_count, 1)
		self.assertEqual(frappe_mock.get_all.call_args.args[0], "Work Order Calculated Item")
		self.assertEqual(frappe_mock.get_all.call_args.kwargs["filters"], {"parent": ["in", ("WO-1",)]})
		load_lots.assert_called_once_with(("LOT-1",))
		load_variants.assert_called_once_with(("BLACK-S",))
		builder.assert_called_once_with(work_orders, calculated_items, lot_contexts, variant_attributes)

	def test_endpoint_uses_supplier_document_name_for_filter_and_returns_supplier_name(self):
		with (
			patch.object(report, "_resolve_process_names", return_value=("Cutting",)),
			patch.object(report, "_get_supplier_work_orders", return_value=[]) as load_work_orders,
			patch.object(report, "frappe") as frappe_mock,
		):
			frappe_mock.get_cached_value.return_value = "King of Garments"
			result = report.get_supplier_pending_report.__wrapped__("SUP-001", "Cutting")

		load_work_orders.assert_called_once_with("SUP-001", ("Cutting",))
		frappe_mock.get_cached_value.assert_called_once_with("Supplier", "SUP-001", "supplier_name")
		self.assertEqual(result["supplier"], "SUP-001")
		self.assertEqual(result["supplier_name"], "King of Garments")

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
		self.assertEqual(row["values"]["S"], {"delivered": 150.0, "received": 60.0, "difference": -90.0})
		self.assertEqual(row["values"]["M"], {"delivered": 100.0, "received": 20.0, "difference": -80.0})
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

		items = report._build_supplier_pending_items(work_orders, calculated_items, lot_contexts, variant_attributes)

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
		)

		rows = items[0]["lots"][0]["rows"]
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["values"]["S"]["delivered"], 30.0)
		self.assertEqual(rows[0]["values"]["S"]["received"], 5.0)

	def test_builder_sorts_unconfigured_sizes_after_ipd_order(self):
		items = report._build_supplier_pending_items(
			[self._work_order("WO-1", "ITEM-A", "LOT-1")],
			[
				self._calculated_item("WO-1", "BLACK-XL", 10, 1, "Black"),
				self._calculated_item("WO-1", "BLACK-L", 10, 1, "Black"),
			],
			{"LOT-1": self._lot_context(is_set_item=False, primary_values=["S", "M"])},
			{
				"BLACK-XL": {"Colour": "Black", "Size": "XL"},
				"BLACK-L": {"Colour": "Black", "Size": "L"},
			},
		)

		self.assertEqual(items[0]["lots"][0]["primary_values"], ["S", "M", "L", "XL"])

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

	@staticmethod
	def _throw_validation(message):
		raise frappe.ValidationError(message)
