# Copyright (c) 2025, Essdee and Contributors
# See license.txt

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.finishing_plan_dispatch import finishing_plan_dispatch


class TestFinishingPlanDispatch(FrappeTestCase):
	@staticmethod
	def _dynamic_row(finishing_plan, batch_dispatches=None):
		return {
			"doc_name": finishing_plan,
			"lot": f"LOT-{finishing_plan}",
			"item": "ITEM-TEST",
			"uom": "Pieces",
			"primary_attribute": "Size",
			"stage": "Packed",
			"values": {
				"S": {
					"qty": 20,
					"row_detail": f"FP-GRN-{finishing_plan}",
					"dispatch_qty": 0,
				},
			},
			"batch_dispatches": batch_dispatches or [],
		}

	@staticmethod
	def _insert_dynamic_grn_batch(
		work_order, lot, dispatched_boxes=0, version=2, ratio=None
	):
		ratio = ratio or {"S": 5}
		suffix = frappe.generate_hash(length=8)
		grn = frappe.get_doc({
			"doctype": "Goods Received Note",
			"name": f"TEST-GRN-{suffix}",
			"docstatus": 1,
			"against": "Work Order",
			"against_id": work_order,
			"lot": lot,
			"packing_calculation_version": version,
		})
		grn.db_insert()
		batch = frappe.get_doc({
			"doctype": "GRN Packing Batch",
			"parent": grn.name,
			"parenttype": "Goods Received Note",
			"parentfield": "packing_batches",
			"batch_id": "BATCH-001",
			"colour": "Navy",
			"box_quantity": 3,
			"dispatched_boxes": dispatched_boxes,
			"pieces_per_box": 5,
			"total_pieces": 15,
			"ratio_json": ratio,
		})
		batch.db_insert()
		frappe.clear_document_cache("Goods Received Note", grn.name)
		return grn, batch

	def test_migrated_legacy_batch_keeps_historical_stock_units(self):
		_grn, batch = self._insert_dynamic_grn_batch(
			"WO-TEST-LEGACY-DISPATCH",
			"LOT-TEST-LEGACY-DISPATCH",
			version=1,
			ratio={"S": 3, "M": 2},
		)
		fp = SimpleNamespace(
			work_order="WO-TEST-LEGACY-DISPATCH",
			lot="LOT-TEST-LEGACY-DISPATCH",
		)
		with patch.object(
			finishing_plan_dispatch.frappe,
			"get_cached_value",
			return_value=("Box", "Pieces"),
		):
			normalized = finishing_plan_dispatch._prepare_dynamic_batch_dispatch(
				fp,
				[{"batch_row": batch.name, "box_quantity": 1}],
			)

		self.assertEqual(normalized[0]["size_pieces"], {"S": 3.0, "M": 2.0})
		self.assertEqual(normalized[0]["stock_quantities"], {"S": 0.6, "M": 0.4})
		self.assertEqual(normalized[0]["stock_uom"], "Box")

	def test_unselected_dynamic_plan_does_not_block_selected_plan(self):
		selected = self._dynamic_row(
			"FP-SELECTED",
			batch_dispatches=[{"batch_row": "BATCH-ROW-1", "box_quantity": 2}],
		)
		untouched = self._dynamic_row("FP-UNTOUCHED")
		doc = frappe.get_doc({
			"doctype": "Finishing Plan Dispatch",
			"finishing_items": frappe.as_json([selected, untouched]),
		})

		def get_fp(_doctype, name):
			return SimpleNamespace(name=name)

		normalized = [{
			"batch_row": "BATCH-ROW-1",
			"grn": "GRN-TEST-1",
			"batch_id": "BATCH-001",
			"colour": "Navy",
			"box_quantity": 2,
			"pieces_per_box": 5,
			"ratio": {"S": 5},
			"size_pieces": {"S": 10},
		}]
		with (
			patch.object(finishing_plan_dispatch.frappe, "get_doc", side_effect=get_fp),
			patch.object(
				finishing_plan_dispatch,
				"get_finishing_packing_summary",
				return_value=frappe._dict(dynamic_ratio_packing=True),
			),
			patch.object(
				finishing_plan_dispatch,
				"_prepare_dynamic_batch_dispatch",
				return_value=normalized,
			) as prepare_dispatch,
			patch.object(finishing_plan_dispatch, "build_variant_attributes", return_value={}),
			patch.object(finishing_plan_dispatch, "get_or_create_variant", return_value="VARIANT-S"),
		):
			doc.before_validate()

		prepare_dispatch.assert_called_once()
		self.assertEqual(prepare_dispatch.call_args.args[0].name, "FP-SELECTED")
		self.assertEqual(
			prepare_dispatch.call_args.args[1],
			[{"batch_row": "BATCH-ROW-1", "box_quantity": 2}],
		)
		self.assertEqual(len(doc.finishing_plan_dispatch_items), 1)
		self.assertEqual(doc.finishing_plan_dispatch_items[0].against_id, "FP-SELECTED")
		self.assertEqual(doc.finishing_plan_dispatch_items[0].quantity, 10)
		batch_dispatches = frappe.parse_json(doc.packing_batch_dispatch_json)
		self.assertEqual(len(batch_dispatches), 1)
		self.assertEqual(batch_dispatches[0]["finishing_plan"], "FP-SELECTED")

	def test_selected_dynamic_batch_still_uses_strict_validation(self):
		doc = frappe.get_doc({
			"doctype": "Finishing Plan Dispatch",
			"finishing_items": frappe.as_json([
				self._dynamic_row(
					"FP-SELECTED",
					batch_dispatches=[{"batch_row": "BATCH-ROW-1", "box_quantity": 3}],
				),
			]),
		})

		with (
			patch.object(
				finishing_plan_dispatch.frappe,
				"get_doc",
				return_value=SimpleNamespace(name="FP-SELECTED"),
			),
			patch.object(
				finishing_plan_dispatch,
				"get_finishing_packing_summary",
				return_value=frappe._dict(dynamic_ratio_packing=True),
			),
			patch.object(
				finishing_plan_dispatch,
				"_prepare_dynamic_batch_dispatch",
				side_effect=frappe.ValidationError(
					"Only 2 boxes are available in GRN-TEST-1 / BATCH-001"
				),
			),
			self.assertRaisesRegex(
				frappe.ValidationError,
				"Only 2 boxes are available",
			),
		):
			doc.before_validate()

	def test_dynamic_batch_validation_uses_submitted_grn_balance(self):
		_grn, batch = self._insert_dynamic_grn_batch(
			"WO-TEST-DYNAMIC-DISPATCH",
			"LOT-TEST-DYNAMIC-DISPATCH",
			dispatched_boxes=1,
		)

		fp = SimpleNamespace(
			work_order="WO-TEST-DYNAMIC-DISPATCH",
			lot="LOT-TEST-DYNAMIC-DISPATCH",
		)
		with patch.object(
			finishing_plan_dispatch.frappe,
			"get_cached_value",
			return_value=("Box", "Pieces"),
		):
			normalized = finishing_plan_dispatch._prepare_dynamic_batch_dispatch(
				fp,
				[{"batch_row": batch.name, "box_quantity": 2}],
			)

		self.assertEqual(normalized[0]["box_quantity"], 2)
		self.assertEqual(normalized[0]["size_pieces"], {"S": 10.0})
		with self.assertRaisesRegex(
			frappe.ValidationError,
			"Only 2 boxes are available",
		):
			with patch.object(
				finishing_plan_dispatch.frappe,
				"get_cached_value",
				return_value=("Box", "Pieces"),
			):
				finishing_plan_dispatch._prepare_dynamic_batch_dispatch(
					fp,
					[{"batch_row": batch.name, "box_quantity": 3}],
				)

	def test_dynamic_dispatch_can_be_saved_and_submitted_with_untouched_plan(self):
		_grn, batch = self._insert_dynamic_grn_batch(
			"WO-FP-SELECTED",
			"LOT-FP-SELECTED",
		)
		selected = self._dynamic_row(
			"FP-SELECTED",
			batch_dispatches=[{"batch_row": batch.name, "box_quantity": 2}],
		)
		untouched = self._dynamic_row("FP-UNTOUCHED")
		doc = frappe.get_doc({
			"doctype": "Finishing Plan Dispatch",
			"naming_series": "FPD-2526-",
			"finishing_items": frappe.as_json([selected, untouched]),
		})
		doc.flags.ignore_links = True

		fp_docs = {
			name: SimpleNamespace(
				name=name,
				lot=f"LOT-{name}",
				work_order=f"WO-{name}",
				pieces_per_box=5,
				finishing_plan_details=[
					SimpleNamespace(item_variant="CUT-VARIANT-S", cutting_qty=100),
				],
			)
			for name in ("FP-SELECTED", "FP-UNTOUCHED")
		}
		original_get_doc = frappe.get_doc
		original_get_value = frappe.get_value

		def get_doc(doctype, *args, **kwargs):
			if doctype == "Finishing Plan":
				return fp_docs[args[0]]
			return original_get_doc(doctype, *args, **kwargs)

		def get_value(doctype, filters=None, fieldname=None, *args, **kwargs):
			if doctype == "Lot" and fieldname == "production_detail":
				return "IPD-TEST"
			if doctype == "Item Production Detail" and fieldname == "primary_item_attribute":
				return "Size"
			if doctype == "Item Production Detail":
				return frappe._dict(
					primary_item_attribute="Size",
					is_set_item=0,
					set_item_attribute=None,
				)
			if doctype == "Finishing Plan GRN Detail":
				return 0
			return original_get_value(doctype, filters, fieldname, *args, **kwargs)

		with (
			patch.object(finishing_plan_dispatch.frappe, "get_doc", side_effect=get_doc),
			patch.object(finishing_plan_dispatch.frappe, "get_value", side_effect=get_value),
			patch.object(
				finishing_plan_dispatch.frappe,
				"get_cached_value",
				return_value=("Box", "Pieces"),
			),
			patch.object(
				finishing_plan_dispatch,
				"get_finishing_packing_summary",
				return_value=frappe._dict(dynamic_ratio_packing=True),
			),
			patch.object(finishing_plan_dispatch, "build_variant_attributes", return_value={}),
			patch.object(finishing_plan_dispatch, "get_or_create_variant", return_value="VARIANT-S"),
			patch.object(finishing_plan_dispatch, "get_variant_attr_details", return_value={"Size": "S"}),
		):
			doc.insert(ignore_permissions=True)
			self.assertEqual(doc.docstatus, 0)
			doc.submit()

		self.assertEqual(doc.docstatus, 1)
		self.assertEqual(len(doc.finishing_plan_dispatch_items), 1)
		self.assertEqual(doc.finishing_plan_dispatch_items[0].against_id, "FP-SELECTED")
		self.assertEqual(doc.finishing_plan_dispatch_items[0].quantity, 10)
		self.assertEqual(doc.finishing_plan_dispatch_items[0].total_dispatched, 10)
		self.assertEqual(doc.fp_total_dispatched, 10)
