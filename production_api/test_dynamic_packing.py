from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.dynamic_packing import aggregate_batch_pieces, normalize_packing_batches
from production_api.patches.v1_0 import migrate_legacy_ratio_packing_grns
from production_api.production_api.doctype.finishing_plan import finishing_plan
from production_api.production_api.doctype.finishing_plan_dispatch import finishing_plan_dispatch
from production_api.production_api.doctype.goods_received_note import goods_received_note
from production_api.production_api.doctype.work_order import work_order


class TestDynamicPacking(FrappeTestCase):
	def test_existing_legacy_plan_can_migrate_and_create_dynamic_grn(self):
		candidate = "FP-2627-00065"
		candidate_plans = migrate_legacy_ratio_packing_grns.get_candidate_plans()
		if candidate in candidate_plans:
			negative_plans = migrate_legacy_ratio_packing_grns.get_negative_packing_plans()
			migrate_legacy_ratio_packing_grns.execute()
		else:
			negative_plans = []
			migrated_grn = frappe.db.exists(
				"Goods Received Note",
				{
					"against_id": frappe.db.get_value("Finishing Plan", candidate, "work_order"),
					"docstatus": 1,
					"packing_calculation_version": 1,
				},
			)
			if not migrated_grn or not frappe.db.exists(
				"GRN Packing Batch", {"parent": migrated_grn}
			):
				self.skipTest("No safe legacy ratio-packing fixture is available on this site")
		for name in negative_plans:
			repaired = frappe.get_doc("Finishing Plan", name)
			self.assertTrue(
				all(row.quantity >= 0 for row in repaired.finishing_plan_grn_details)
			)
		fp = frappe.get_doc("Finishing Plan", candidate)
		finishing_plan._validate_dynamic_packing_transition(fp.work_order, fp.lot)
		legacy_summary = finishing_plan.get_finishing_packing_summary(fp)
		self.assertTrue(legacy_summary.dynamic_ratio_packing)
		self.assertEqual(legacy_summary.total_packed_boxes, 60)
		self.assertEqual(legacy_summary.total_packed, 720)

		with patch.object(
			goods_received_note.frappe,
			"get_user",
			return_value=SimpleNamespace(doc=SimpleNamespace(name="Administrator")),
		):
			grn_name = finishing_plan.create_grn(
				fp.work_order,
				fp.lot,
				fp.item,
				{},
				"S-0171",
				frappe.utils.nowdate(),
				packing_batches=[{
					"colour": "Red",
					"box_quantity": 1,
					"ratio": {"S": 3, "M": 3, "L": 2, "XL": 2, "2XL": 2},
				}],
			)
		grn = frappe.get_doc("Goods Received Note", grn_name)
		self.assertEqual(grn.docstatus, 1)
		self.assertEqual(grn.packing_calculation_version, 2)
		self.assertEqual(grn.total_packing_boxes, 1)
		self.assertEqual(grn.total_packing_pieces, 12)

		goods_received_note.update_finishing_item_doc(grn.name, fp.name, True)
		fp.reload()
		combined_summary = finishing_plan.get_finishing_packing_summary(fp)
		self.assertEqual(combined_summary.total_packed_boxes, 61)
		self.assertEqual(combined_summary.total_packed, 732)

		rows = finishing_plan_dispatch.fetch_fp_items()
		selected = next(row for row in rows if row["doc_name"] == candidate)
		legacy_batch = next(
			batch for batch in selected["packing_batches"]
			if batch.get("packing_calculation_version") == 1
		)
		dynamic_batch = next(
			batch for batch in selected["packing_batches"]
			if batch.get("packing_calculation_version") == 2
			and batch.get("grn") == grn.name
		)
		selected["batch_dispatches"] = [
			{
				"batch_row": legacy_batch["batch_row"],
				"box_quantity": 1,
			},
			{
				"batch_row": dynamic_batch["batch_row"],
				"box_quantity": 1,
			},
		]
		untouched = next(
			row for row in rows
			if row["doc_name"] != candidate and row.get("dynamic_ratio_packing")
		)
		fpd = frappe.get_doc({
			"doctype": "Finishing Plan Dispatch",
			"naming_series": "FPD-2526-",
			"finishing_items": frappe.as_json([selected, untouched]),
		})
		fpd.insert(ignore_permissions=True)
		self.assertFalse(any(row.quantity == 0 for row in fpd.finishing_plan_dispatch_items))

		fpd.reload()
		fpd.onload()
		reloaded_items = fpd.get_onload("items")
		reloaded_selected = next(
			row for row in reloaded_items if row["doc_name"] == candidate
		)
		self.assertEqual(
			reloaded_selected["batch_dispatches"],
			selected["batch_dispatches"],
		)
		self.assertIn(
			untouched["doc_name"],
			{row["doc_name"] for row in reloaded_items},
		)
		fpd.finishing_items = frappe.as_json(reloaded_items)
		fpd.submit()
		self.assertEqual(fpd.docstatus, 1)
		self.assertTrue(fpd.finishing_plan_dispatch_items)
		self.assertEqual(
			{row.against_id for row in fpd.finishing_plan_dispatch_items},
			{candidate},
		)
		self.assertAlmostEqual(
			sum(row.quantity for row in fpd.finishing_plan_dispatch_items),
			13,
		)
		self.assertEqual(
			sum(row.packing_piece_quantity for row in fpd.finishing_plan_dispatch_items),
			24,
		)

		with patch.object(
			goods_received_note.frappe,
			"get_user",
			return_value=SimpleNamespace(doc=SimpleNamespace(name="Administrator")),
		):
			finishing_plan_dispatch.create_stock_dispatch(
				fpd.name,
				"S-0171",
				"S-0167",
				"TEST-VEHICLE",
				0,
			)

		fpd.reload()
		self.assertTrue(fpd.stock_entry)
		self.assertEqual(frappe.db.get_value("Stock Entry", fpd.stock_entry, "docstatus"), 1)
		self.assertEqual(
			frappe.db.get_value("GRN Packing Batch", legacy_batch["batch_row"], "dispatched_boxes"),
			1,
		)
		self.assertEqual(
			frappe.db.get_value("GRN Packing Batch", dynamic_batch["batch_row"], "dispatched_boxes"),
			1,
		)
		fp.reload()
		self.assertEqual(
			finishing_plan.get_finishing_packing_summary(fp).total_dispatched,
			24,
		)

		stock_entry = fpd.stock_entry
		fpd.cancel()
		self.assertEqual(fpd.docstatus, 2)
		self.assertEqual(frappe.db.get_value("Stock Entry", stock_entry, "docstatus"), 2)
		self.assertEqual(
			frappe.db.get_value("GRN Packing Batch", legacy_batch["batch_row"], "dispatched_boxes"),
			0,
		)
		self.assertEqual(
			frappe.db.get_value("GRN Packing Batch", dynamic_batch["batch_row"], "dispatched_boxes"),
			0,
		)
		fp.reload()
		self.assertEqual(
			finishing_plan.get_finishing_packing_summary(fp).total_dispatched,
			0,
		)

	def test_legacy_fixed_ratio_is_reconstructed_from_fractional_box_rows(self):
		ratio = migrate_legacy_ratio_packing_grns.reconstruct_ratio(
			"GRN-LEGACY-TEST",
			{
				"S": 14.5 * 12,
				"M": 14.5 * 12,
				"L": (58 / 6) * 12,
				"XL": (58 / 6) * 12,
				"2XL": (58 / 6) * 12,
			},
			58,
			12,
		)

		self.assertEqual(ratio, {"S": 3, "M": 3, "L": 2, "XL": 2, "2XL": 2})

	def test_inexact_legacy_ratio_is_rejected(self):
		with self.assertRaisesRegex(
			frappe.ValidationError,
			"cannot be reconstructed exactly",
		):
			migrate_legacy_ratio_packing_grns.reconstruct_ratio(
				"GRN-LEGACY-TEST",
				{"S": 7, "M": 5},
				2,
				6,
			)

	def test_batches_are_aggregated_as_exact_size_pieces(self):
		batches = normalize_packing_batches(
			[
				{"batch_id": "A", "colour": "Green", "box_quantity": 2, "ratio": {"S": 2, "M": 3}},
				{"batch_id": "B", "colour": "Green", "box_quantity": 1, "ratio": {"M": 1, "L": 4}},
			],
			["S", "M", "L"],
			["Green"],
			5,
		)

		sizes, boxes, pieces = aggregate_batch_pieces(batches)
		self.assertEqual(sizes, {"S": 4.0, "M": 7.0, "L": 4.0})
		self.assertEqual(boxes, 3.0)
		self.assertEqual(pieces, 15.0)

	def test_each_batch_must_match_configured_pieces_per_box(self):
		with self.assertRaisesRegex(
			frappe.ValidationError,
			"total pieces per box should be 10.*totals 9",
		):
			normalize_packing_batches(
				[
					{
						"colour": "Green",
						"box_quantity": 1,
						"ratio": {"S": 2, "M": 3, "L": 4},
					}
				],
				["S", "M", "L"],
				["Green"],
				10,
			)

	def test_work_order_receivables_keep_legacy_fixed_ratio_flow(self):
		ipd = self._ipd(based_on_other_attribute_mapping=0)
		receivables, total = self._get_receivables(ipd)

		self.assertEqual(self._quantities(receivables), {"S": 4.0, "M": 2.0})
		self.assertEqual(total, 6.0)

	def test_work_order_receivables_expose_all_pieces_only_for_dynamic_flow(self):
		ipd = self._ipd(based_on_other_attribute_mapping=1)
		receivables, total = self._get_receivables(ipd)

		self.assertEqual(self._quantities(receivables), {"S": 5.0, "M": 4.0})
		self.assertEqual(total, 9.0)

	@staticmethod
	def _ipd(based_on_other_attribute_mapping):
		return SimpleNamespace(
			name="IPD-TEST",
			item="ITEM-TEST",
			primary_item_attribute="Size",
			packing_attribute="Colour",
			pack_out_stage="Pack",
			packing_mode="Size Ratio Packing",
			based_on_other_attribute_mapping=based_on_other_attribute_mapping,
			packing_size_details=[
				SimpleNamespace(attribute_value="S", quantity=2),
				SimpleNamespace(attribute_value="M", quantity=1),
			],
		)

	@staticmethod
	def _get_receivables(ipd):
		item_list = {
			"ITEM-TEST": [
				{"item_variant": "IN-S", "qty": 5},
				{"item_variant": "IN-M", "qty": 4},
			]
		}
		attributes = {
			"IN-S": {"Size": "S", "Colour": "Green"},
			"IN-M": {"Size": "M", "Colour": "Green"},
		}
		with (
			patch.object(work_order, "get_variant_attr_details", side_effect=lambda item: attributes[item]),
			patch.object(work_order, "build_variant_attributes", side_effect=lambda attrs, *_args: attrs),
			patch.object(work_order, "get_or_create_variant", side_effect=lambda _item, attrs: f"OUT-{attrs['Size']}"),
			patch.object(work_order.frappe, "msgprint"),
		):
			return work_order.get_size_wise_packing_receivables(
				item_list, ipd, "LOT-TEST", "Pieces"
			)

	@staticmethod
	def _quantities(receivables):
		return {row["item_variant"].removeprefix("OUT-"): row["qty"] for row in receivables}
