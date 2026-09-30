# Copyright (c) 2025, Essdee and Contributors
# See license.txt

from unittest.mock import MagicMock, call, patch
from types import SimpleNamespace

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.finishing_plan import finishing_plan
from production_api import utils as production_utils
from production_api.patches.v1_0 import (
	close_production_orders_for_existing_ocr_completed_plans as close_existing_orders_patch,
	migrate_ocr_requested_to_ready_for_audit as audit_workflow_patch,
)


class TestFinishingPlan(FrappeTestCase):
	def test_daily_job_auto_closes_only_audits_older_than_30_days(self):
		with (
			patch.object(finishing_plan, "today", return_value="2026-09-28"),
			patch.object(
				finishing_plan.frappe,
				"get_all",
				return_value=["FP-OLD-1", "FP-OLD-2"],
			) as get_all,
			patch.object(finishing_plan.frappe.db, "set_value") as set_value,
			patch.object(
				finishing_plan,
				"close_linked_production_order_if_all_lots_audited",
			) as close_production_order,
		):
			auto_closed = (
				finishing_plan.auto_close_audited_finishing_plans_after_30_days()
			)

		get_all.assert_called_once_with(
			"Finishing Plan",
			filters={
				"fp_status": "Audit Completed",
				"audit_completed_date": ("<", "2026-08-29"),
			},
			pluck="name",
		)
		self.assertEqual(set_value.call_count, 2)
		set_value.assert_any_call(
			"Finishing Plan", "FP-OLD-1", "fp_status", "Auto Closed"
		)
		set_value.assert_any_call(
			"Finishing Plan", "FP-OLD-2", "fp_status", "Auto Closed"
		)
		close_production_order.assert_not_called()
		self.assertEqual(auto_closed, 2)

	def test_audit_request_moves_dispatched_plan_to_ready_for_audit(self):
		doc = MagicMock(fp_status="Dispatched")
		with (
			patch.object(finishing_plan.frappe, "get_doc", return_value=doc) as get_doc,
			patch.object(finishing_plan, "today", return_value="2026-09-28"),
		):
			result = finishing_plan.request_audit("FP-1")

		get_doc.assert_called_once_with("Finishing Plan", "FP-1", for_update=True)
		self.assertEqual(doc.fp_status, "Ready for Audit")
		self.assertEqual(doc.audit_requested_date, "2026-09-28")
		self.assertIsNone(doc.audit_completed_date)
		doc.save.assert_called_once_with(ignore_permissions=True)
		self.assertEqual(result["fp_status"], "Ready for Audit")

	def test_accounts_role_can_complete_audit(self):
		doc = MagicMock(fp_status="Ready for Audit", lot="LOT-1")
		with (
			patch.object(finishing_plan, "require_accounts_user_role") as require_role,
			patch.object(finishing_plan.frappe, "get_doc", return_value=doc),
			patch.object(finishing_plan, "today", return_value="2026-09-28"),
			patch.object(
				finishing_plan,
				"close_linked_production_order_if_all_lots_audited",
			) as close_production_order,
		):
			result = finishing_plan.complete_audit("FP-1")

		require_role.assert_called_once_with()
		self.assertEqual(doc.fp_status, "Audit Completed")
		self.assertEqual(doc.audit_completed_date, "2026-09-28")
		doc.save.assert_called_once_with(ignore_permissions=True)
		close_production_order.assert_called_once_with("LOT-1")
		self.assertEqual(result["fp_status"], "Audit Completed")

	def test_audit_completion_rejects_user_without_configured_accounts_role(self):
		with (
			patch.object(
				finishing_plan.frappe.db,
				"get_single_value",
				return_value="Accounts User",
			),
			patch.object(finishing_plan.frappe, "get_roles", return_value=["Stock User"]),
		):
			with self.assertRaisesRegex(frappe.ValidationError, "Accounts User"):
				finishing_plan.require_accounts_user_role()

	def test_system_manager_completes_ocr_only_after_audit(self):
		doc = MagicMock(fp_status="Audit Completed", lot="LOT-1")
		with (
			patch.object(finishing_plan.frappe, "get_roles", return_value=["System Manager"]),
			patch.object(finishing_plan.frappe, "get_doc", return_value=doc),
			patch.object(
				finishing_plan,
				"close_linked_production_order_if_all_lots_audited",
			) as close_production_order,
		):
			result = finishing_plan.complete_ocr("FP-1")

		self.assertEqual(doc.fp_status, "OCR Completed")
		doc.save.assert_called_once_with(ignore_permissions=True)
		close_production_order.assert_called_once_with("LOT-1")
		self.assertEqual(result["fp_status"], "OCR Completed")

	def test_system_manager_completes_ocr_from_auto_closed(self):
		doc = MagicMock(fp_status="Auto Closed", lot="LOT-1")
		with (
			patch.object(finishing_plan.frappe, "get_roles", return_value=["System Manager"]),
			patch.object(finishing_plan.frappe, "get_doc", return_value=doc),
			patch.object(
				finishing_plan,
				"close_linked_production_order_if_all_lots_audited",
			) as close_production_order,
		):
			result = finishing_plan.complete_ocr("FP-1")

		self.assertEqual(doc.fp_status, "OCR Completed")
		doc.save.assert_called_once_with(ignore_permissions=True)
		close_production_order.assert_called_once_with("LOT-1")
		self.assertEqual(result["fp_status"], "OCR Completed")

	def test_non_system_manager_cannot_complete_ocr(self):
		with patch.object(
			finishing_plan.frappe,
			"get_roles",
			return_value=["Accounts User"],
		):
			with self.assertRaisesRegex(frappe.ValidationError, "System Manager"):
				finishing_plan.complete_ocr("FP-1")

	def test_legacy_ocr_request_patch_uses_modified_date_as_request_date(self):
		legacy_row = frappe._dict(
			name="FP-OLD",
			lot="LOT-1",
			modified="2026-09-27 14:30:00",
			audit_requested_date=None,
		)
		with (
			patch.object(
				audit_workflow_patch.frappe.db,
				"get_single_value",
				return_value=None,
			),
			patch.object(
				audit_workflow_patch.frappe.db,
				"exists",
				return_value=True,
			),
			patch.object(
				audit_workflow_patch.frappe.db,
				"set_single_value",
			) as set_single_value,
			patch.object(
				audit_workflow_patch.frappe,
				"get_all",
				side_effect=[
					[legacy_row],
					[frappe._dict(production_order="PPO-1")],
				],
			),
			patch.object(
				audit_workflow_patch,
				"today",
				return_value="2026-09-28",
			),
			patch.object(
				audit_workflow_patch,
				"close_production_order_if_all_lots_audited",
			) as close_production_order,
			patch.object(audit_workflow_patch.frappe.db, "set_value") as set_value,
			patch.object(audit_workflow_patch.frappe.db, "commit"),
		):
			audit_workflow_patch.execute()

		values = set_value.call_args.args[2]
		set_single_value.assert_called_once_with(
			"MRP Settings", "accounts_user_role", "Accounts User"
		)
		self.assertEqual(values["fp_status"], "Ready for Audit")
		self.assertEqual(str(values["audit_requested_date"]), "2026-09-27")
		self.assertFalse(set_value.call_args.kwargs["update_modified"])
		close_production_order.assert_called_once_with("PPO-1")

	def test_legacy_audit_request_older_than_30_days_is_ocr_completed(self):
		legacy_row = frappe._dict(
			name="FP-OLD",
			lot=None,
			modified="2026-09-01 14:30:00",
			audit_requested_date="2026-08-28",
		)
		with (
			patch.object(
				audit_workflow_patch.frappe.db,
				"get_single_value",
				return_value="Accounts User",
			),
			patch.object(
				audit_workflow_patch.frappe,
				"get_all",
				return_value=[legacy_row],
			),
			patch.object(
				audit_workflow_patch,
				"today",
				return_value="2026-09-28",
			),
			patch.object(audit_workflow_patch.frappe.db, "set_value") as set_value,
			patch.object(audit_workflow_patch.frappe.db, "commit"),
		):
			audit_workflow_patch.execute()

		values = set_value.call_args.args[2]
		self.assertEqual(values["fp_status"], "OCR Completed")
		self.assertEqual(str(values["audit_requested_date"]), "2026-08-28")
		self.assertEqual(values["audit_completed_date"], "2026-09-28")

	def test_existing_ocr_completed_patch_checks_each_related_production_order(self):
		with (
			patch.object(
				close_existing_orders_patch.frappe,
				"get_all",
				side_effect=[
					["LOT-2", "LOT-1", "LOT-1"],
					["PPO-2", "PPO-1", "PPO-1"],
				],
			) as get_all,
			patch.object(
				close_existing_orders_patch,
				"close_production_order_if_all_lots_audited",
			) as close_production_order,
			patch.object(close_existing_orders_patch.frappe.db, "commit") as commit,
		):
			close_existing_orders_patch.execute()

		self.assertEqual(
			get_all.call_args_list,
			[
				call(
					"Finishing Plan",
					filters={
						"fp_status": "OCR Completed",
						"lot": ("is", "set"),
					},
					pluck="lot",
				),
				call(
					"Lot",
					filters={
						"name": ("in", ["LOT-1", "LOT-2"]),
						"production_order": ("is", "set"),
					},
					pluck="production_order",
				),
			],
		)
		self.assertEqual(
			close_production_order.call_args_list,
			[call("PPO-1"), call("PPO-2")],
		)
		commit.assert_called_once_with()

	def test_packing_dpr_multiplies_set_pieces_but_not_box_values(self):
		ipd_doc = frappe._dict(
			name="IPD-SET",
			is_set_item=1,
			set_item_combination_details=[
				frappe._dict(set_item_attribute_value="Top"),
				frappe._dict(set_item_attribute_value="Bottom"),
				frappe._dict(set_item_attribute_value="Top"),
			],
		)
		packing = frappe._dict(
			sizes=["S"],
			size_pieces={"S": 100},
			pieces_per_box=5,
			dynamic_ratio_packing=False,
			total_boxes=20,
			total_pieces=100,
		)

		with (
			patch.object(
				finishing_plan.frappe,
				"get_all",
				return_value=[frappe._dict(name="GRN-SET", lot="LOT-SET")],
			),
			patch.object(
				finishing_plan.frappe,
				"get_value",
				side_effect=["SET-ITEM", "IPD-SET"],
			),
			patch.object(
				finishing_plan.frappe,
				"get_cached_doc",
				return_value=ipd_doc,
			),
			patch.object(
				finishing_plan,
				"_get_packing_grn_report_values",
				return_value=packing,
			),
		):
			result = finishing_plan.get_finishing_packed_details("2026-08-10")

		row = result["data"][0]
		self.assertEqual(row["size_qty"], {"S": 200})
		self.assertEqual(row["total_pieces"], 200)
		self.assertEqual(row["pieces_per_box"], 5)
		self.assertEqual(row["total_boxes"], 20)

	def test_packing_dpr_summary_splits_the_same_lot_by_actual_date(self):
		grns = [
			frappe._dict(name="GRN-DAY-1", lot="LOT-1", actual_date="2026-09-01"),
			frappe._dict(name="GRN-DAY-2", lot="LOT-1", actual_date="2026-09-02"),
		]
		packing_rows = [
			frappe._dict(
				sizes=["S"], size_pieces={"S": 10}, pieces_per_box=5,
				dynamic_ratio_packing=False, total_boxes=2, total_pieces=10,
			),
			frappe._dict(
				sizes=["S"], size_pieces={"S": 15}, pieces_per_box=5,
				dynamic_ratio_packing=False, total_boxes=3, total_pieces=15,
			),
		]
		ipd_doc = frappe._dict(is_set_item=0)

		with (
			patch.object(finishing_plan.frappe, "get_all", return_value=grns) as get_all,
			patch.object(
				finishing_plan.frappe,
				"get_value",
				side_effect=["ITEM-1", "IPD-1", "ITEM-1", "IPD-1"],
			),
			patch.object(finishing_plan.frappe, "get_cached_doc", return_value=ipd_doc),
			patch.object(
				finishing_plan,
				"_get_packing_grn_report_values",
				side_effect=packing_rows,
			),
		):
			result = finishing_plan.get_finishing_packed_details(
				from_date="2026-09-01",
				to_date="2026-09-02",
				lot_list=["LOT-1"],
				item_list=["ITEM-1"],
				summary=1,
			)

		self.assertEqual([row["date"] for row in result["data"]], [
			"2026-09-01", "2026-09-02",
		])
		self.assertEqual([row["total_pieces"] for row in result["data"]], [10, 15])
		filters = get_all.call_args.kwargs["filters"]
		self.assertEqual(
			filters["actual_date"],
			["between", ["2026-09-01", "2026-09-02"]],
		)

	def test_ironing_dpr_keeps_set_parts_with_same_colour_separate(self):
		dc_docs = {}
		for name, part in (("DC-TOP", "Top"), ("DC-BOTTOM", "Bottom")):
			doc = MagicMock()
			doc.name = name
			doc.lot = "LOT-SET"
			doc.item = "SET-ITEM"
			doc.production_detail = "IPD-SET"
			doc.items = part
			doc.get.side_effect = lambda fieldname, current_doc=doc: getattr(
				current_doc, fieldname
			)
			dc_docs[name] = doc

		def get_doc(doctype, name):
			if doctype == "Delivery Challan":
				return dc_docs[name]
			if doctype == "Lot":
				return SimpleNamespace(production_detail="IPD-SET")
			raise AssertionError((doctype, name))

		def fetch_item_details(items, _ipd, _lot):
			qty = 10 if items == "Top" else 8
			return [{
				"primary_attribute_values": ["S"],
				"items": [{
					"attributes": {"Colour": "Navy", "Part": items},
					"values": {"S": {"delivered_quantity": qty}},
				}],
			}]

		with (
			patch.object(
				production_utils.frappe.db,
				"get_single_value",
				return_value="Ironing",
			),
			patch.object(
				production_utils.frappe.db,
				"sql",
				side_effect=[
					[],
					[frappe._dict(name="DC-TOP"), frappe._dict(name="DC-BOTTOM")],
				],
			),
			patch.object(
				production_utils.frappe,
				"get_single",
				return_value=frappe._dict(
					default_packing_attribute="Colour",
					default_set_item_attribute="Wrong Global Part Attribute",
				),
			),
			patch.object(production_utils.frappe, "get_doc", side_effect=get_doc),
			patch.object(
				production_utils.frappe,
				"get_value",
				return_value=frappe._dict(
					is_set_item=1,
					set_item_attribute="Part",
				),
			),
			patch(
				"production_api.production_api.doctype.delivery_challan.delivery_challan.fetch_item_details",
				side_effect=fetch_item_details,
			),
		):
			result = production_utils.dc_dpr_report(date="2026-08-10")

		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["attributes"], ["Colour", "Part"])
		rows_by_part = {row["part"]: row for row in result[0]["rows"]}
		self.assertEqual(set(rows_by_part), {"Top", "Bottom"})
		self.assertEqual(rows_by_part["Top"]["S"], 10)
		self.assertEqual(rows_by_part["Top"]["total_qty"], 10)
		self.assertEqual(rows_by_part["Bottom"]["S"], 8)
		self.assertEqual(rows_by_part["Bottom"]["total_qty"], 8)

	def test_ironing_dpr_summary_splits_the_same_lot_by_actual_date(self):
		dc_docs = {}
		for name, qty in (("DC-DAY-1", 10), ("DC-DAY-2", 15)):
			doc = MagicMock()
			doc.name = name
			doc.lot = "LOT-1"
			doc.item = "ITEM-1"
			doc.production_detail = "IPD-1"
			doc.items = qty
			doc.get.side_effect = lambda fieldname, current_doc=doc: getattr(
				current_doc, fieldname, None
			)
			dc_docs[name] = doc

		def get_doc(doctype, name):
			if doctype == "Delivery Challan":
				return dc_docs[name]
			if doctype == "Lot":
				return SimpleNamespace(production_detail="IPD-1")
			raise AssertionError((doctype, name))

		def fetch_item_details(qty, _ipd, _lot):
			return [{
				"primary_attribute_values": ["S"],
				"items": [{
					"attributes": {"Colour": "Navy"},
					"values": {"S": {"delivered_quantity": qty}},
				}],
			}]

		with (
			patch.object(
				production_utils.frappe.db,
				"get_single_value",
				return_value="Ironing",
			),
			patch.object(
				production_utils.frappe.db,
				"sql",
				side_effect=[
					[],
					[
						frappe._dict(name="DC-DAY-1", actual_date="2026-09-01"),
						frappe._dict(name="DC-DAY-2", actual_date="2026-09-02"),
					],
				],
			) as sql,
			patch.object(
				production_utils.frappe,
				"get_single",
				return_value=frappe._dict(
					default_packing_attribute="Colour",
					default_set_item_attribute="Part",
				),
			),
			patch.object(production_utils.frappe, "get_doc", side_effect=get_doc),
			patch.object(
				production_utils.frappe,
				"get_value",
				return_value=frappe._dict(is_set_item=0, set_item_attribute=None),
			),
			patch(
				"production_api.production_api.doctype.delivery_challan.delivery_challan.fetch_item_details",
				side_effect=fetch_item_details,
			),
		):
			result = production_utils.dc_dpr_report(
				from_date="2026-09-01",
				to_date="2026-09-02",
				lot=["LOT-1"],
				item=["ITEM-1"],
				summary=1,
			)

		self.assertEqual([row["date"] for row in result], ["2026-09-01", "2026-09-02"])
		self.assertEqual([row["rows"][0]["total_qty"] for row in result], [10, 15])
		query, values = sql.call_args_list[1].args[:2]
		self.assertIn("t1.actual_date BETWEEN %(from_date)s AND %(to_date)s", query)
		self.assertEqual(values["from_date"], "2026-09-01")
		self.assertEqual(values["to_date"], "2026-09-02")
		self.assertEqual(values["lot"], ("LOT-1",))
		self.assertEqual(values["item"], ("ITEM-1",))

	def _get_ocr_test_doc(self):
		return frappe._dict(
			lot="LOT-TEST",
			pieces_per_box=5,
			finishing_plan_details=[
				frappe._dict(
					item_variant="VARIANT-S",
					set_combination={"major_colour": "Blue"},
					cutting_qty=10,
					dc_qty=10,
					transferred_qty=0,
					ironing_excess=0,
					lot_transferred=0,
					delivered_quantity=10,
					return_qty=0,
					pack_return_qty=0,
					rejected_qty=0,
				),
			],
			finishing_plan_grn_details=[
				frappe._dict(item_variant="VARIANT-S", quantity=2, dispatched=1),
			],
			finishing_plan_reworked_details=[],
			finishing_old_lot_given_items=[],
			finishing_old_lot_received_items=[],
		)

	def _get_ocr_value(self, doctype, name, fields):
		if doctype == "Lot":
			return "IPD-TEST"
		if doctype == "Item Production Detail":
			return (0, "Colour", "Size", None)
		raise AssertionError((doctype, name, fields))

	def test_legacy_ocr_totals_include_packed_and_dispatched_boxes(self):
		doc = self._get_ocr_test_doc()
		packing_summary = frappe._dict(dynamic_ratio_packing=False, sizes={})
		with (
			patch.object(finishing_plan.frappe, "get_value", side_effect=self._get_ocr_value),
			patch.object(
				finishing_plan, "get_variant_attr_details",
				return_value={"Colour": "Blue", "Size": "S"},
			),
			patch.object(
				finishing_plan, "get_finishing_packing_summary",
				return_value=packing_summary,
			),
			patch.object(
				finishing_plan.frappe, "get_cached_doc",
				return_value=frappe._dict(lot_order_details=[]),
			),
		):
			ocr = finishing_plan.get_ocr_details(doc)["Item"]

		packed_by_size = sum(row["packed_box"] for row in ocr["total"].values())
		dispatched_by_size = sum(
			row["dispatched_box"] for row in ocr["total"].values()
		)
		self.assertEqual(packed_by_size, 2)
		self.assertEqual(dispatched_by_size, 1)
		self.assertEqual(ocr["packed_box"], packed_by_size)
		self.assertEqual(ocr["dispatched_box"], dispatched_by_size)

	def test_dynamic_ocr_totals_use_physical_batch_box_totals(self):
		doc = self._get_ocr_test_doc()
		packing_summary = frappe._dict(
			dynamic_ratio_packing=True,
			total_packed_boxes=3,
			total_dispatched_boxes=2,
			sizes={"S": {"packed": 10, "dispatched": 5, "packed_boxes": 5, "dispatched_boxes": 4}},
		)
		with (
			patch.object(finishing_plan.frappe, "get_value", side_effect=self._get_ocr_value),
			patch.object(
				finishing_plan, "get_variant_attr_details",
				return_value={"Colour": "Blue", "Size": "S"},
			),
			patch.object(
				finishing_plan, "get_finishing_packing_summary",
				return_value=packing_summary,
			),
			patch.object(
				finishing_plan.frappe, "get_cached_doc",
				return_value=frappe._dict(lot_order_details=[]),
			),
		):
			ocr = finishing_plan.get_ocr_details(doc)["Item"]

		self.assertEqual(ocr["packed_box"], packing_summary.total_packed_boxes)
		self.assertEqual(
			ocr["dispatched_box"], packing_summary.total_dispatched_boxes
		)

	def test_old_lot_given_is_counted_as_transferred_loose_piece(self):
		doc = self._get_ocr_test_doc()
		doc.finishing_plan_grn_details = []
		doc.finishing_plan_details[0].return_qty = 4
		doc.finishing_plan_details[0].pack_return_qty = 6
		doc.finishing_old_lot_given_items = [frappe._dict(
			item_variant="VARIANT-S",
			set_combination={"major_colour": "Blue"},
			loose_piece_given=1,
			loose_piece_set_given=2,
			lot_transfer=None,
		)]
		packing_summary = frappe._dict(dynamic_ratio_packing=False, sizes={})

		with (
			patch.object(finishing_plan.frappe, "get_value", side_effect=self._get_ocr_value),
			patch.object(
				finishing_plan, "get_variant_attr_details",
				return_value={"Colour": "Blue", "Size": "S"},
			),
			patch.object(
				finishing_plan, "get_finishing_packing_summary",
				return_value=packing_summary,
			),
			patch.object(
				finishing_plan.frappe, "get_cached_doc",
				return_value=frappe._dict(lot_order_details=[]),
			),
		):
			ocr = finishing_plan.get_ocr_details(doc)["Item"]
			unaccountable = finishing_plan._total_unaccountable(doc)

		self.assertEqual(ocr["loose_piece"], 3)
		self.assertEqual(ocr["loose_piece_set"], 4)
		self.assertEqual(ocr["transferred_as_loose_piece"], 3)
		self.assertEqual(ocr["total"]["S"]["transferred_as_loose_piece"], 3)
		self.assertEqual(unaccountable, 0)

	def test_fetch_old_lot_does_not_filter_sources_by_ocr_status(self):
		destination = MagicMock()
		destination.name = "FP-DEST"
		destination.item = "ITEM-1"
		destination.lot = "LOT-DEST"
		destination.fp_status = "Planned"
		destination.finishing_plan_details = []
		destination.finishing_old_lot_items = []
		destination.set.side_effect = lambda fieldname, value: setattr(
			destination, fieldname, value
		)
		ipd = frappe._dict(
			name="IPD-1",
			packing_attribute="Colour",
			primary_item_attribute="Size",
			set_item_attribute=None,
			is_set_item=0,
			packing_attribute_details=[],
		)

		def get_doc(doctype, name):
			return destination if doctype == "Finishing Plan" else ipd

		with (
			patch.object(finishing_plan.frappe, "get_doc", side_effect=get_doc),
			patch.object(finishing_plan.frappe, "get_value", return_value="IPD-1"),
			patch.object(finishing_plan.frappe, "get_all", return_value=[]) as get_all,
			patch.object(finishing_plan, "get_ipd_primary_values", return_value=[]),
		):
			finishing_plan.fetch_from_old_lot("FP-DEST")

		filters = get_all.call_args.kwargs["filters"]
		self.assertNotIn("fp_status", filters)
		self.assertEqual(filters["item"], "ITEM-1")

	def test_fetch_old_lot_can_refresh_the_remaining_balance_repeatedly(self):
		destination = MagicMock()
		destination.name = "FP-DEST"
		destination.item = "ITEM-1"
		destination.lot = "LOT-DEST"
		destination.fp_status = "Planned"
		destination.finishing_plan_details = [
			frappe._dict(item_variant="VARIANT-S")
		]
		destination.finishing_old_lot_items = [
			frappe._dict(item_variant="STALE-VARIANT")
		]
		source = frappe._dict(
			lot="LOT-SOURCE",
			delivery_location="WH-1",
			finishing_plan_details=[
				frappe._dict(
					item_variant="VARIANT-S",
					return_qty=10,
					pack_return_qty=4,
				),
			],
			finishing_old_lot_given_items=[
				frappe._dict(
					item_variant="VARIANT-S",
					loose_piece_given=2,
					loose_piece_set_given=1,
					lot_transfer=None,
				),
			],
		)
		ipd = frappe._dict(
			name="IPD-1",
			packing_attribute="Colour",
			primary_item_attribute="Size",
			set_item_attribute=None,
			is_set_item=0,
			major_attribute_value=None,
			packing_attribute_details=[frappe._dict(attribute_value="Blue")],
		)

		def get_doc(doctype, name):
			if doctype == "Finishing Plan":
				return destination if name == "FP-DEST" else source
			if doctype == "Item Production Detail":
				return ipd
			raise AssertionError((doctype, name))

		with (
			patch.object(finishing_plan.frappe, "get_doc", side_effect=get_doc),
			patch.object(finishing_plan.frappe, "get_value", return_value="IPD-1"),
			patch.object(finishing_plan.frappe, "get_all", return_value=["FP-SOURCE"]),
			patch.object(finishing_plan.frappe.db, "get_value", return_value="Warehouse 1"),
			patch.object(
				finishing_plan,
				"get_variant_attr_details",
				return_value={"Colour": "Blue", "Size": "S"},
			),
			patch.object(finishing_plan, "get_ipd_primary_values", return_value=["S"]),
		):
			first_result = finishing_plan.fetch_from_old_lot("FP-DEST")
			first_cell = first_result["data"][0]["old_lot_inward"]["data"]["Blue"]["values"]["S"]
			self.assertEqual(first_cell["balance_loose_piece"], 8)
			self.assertEqual(first_cell["balance_loose_piece_set"], 3)

			source.finishing_old_lot_given_items.append(frappe._dict(
				item_variant="VARIANT-S",
				loose_piece_given=3,
				loose_piece_set_given=1,
				lot_transfer=None,
			))
			second_result = finishing_plan.fetch_from_old_lot("FP-DEST")

		second_cell = second_result["data"][0]["old_lot_inward"]["data"]["Blue"]["values"]["S"]
		self.assertEqual(second_cell["balance_loose_piece"], 5)
		self.assertEqual(second_cell["balance_loose_piece_set"], 2)
		# Fetching is display-only and does not replace or save child rows.
		self.assertEqual(len(destination.finishing_old_lot_items), 1)
		self.assertEqual(destination.finishing_old_lot_items[0].item_variant, "STALE-VARIANT")
		destination.save.assert_not_called()

	def test_cancelled_lot_transfer_tracking_is_removed_from_both_plans(self):
		source = MagicMock()
		source_rows = [
			frappe._dict(lot_transfer="LT-CANCEL"),
			frappe._dict(lot_transfer="LT-KEEP"),
		]
		source.get.return_value = source_rows
		source.set.side_effect = lambda fieldname, value: setattr(source, fieldname, value)
		destination = MagicMock()
		destination_rows = [frappe._dict(lot_transfer="LT-CANCEL")]
		destination.get.return_value = destination_rows
		destination.set.side_effect = lambda fieldname, value: setattr(
			destination, fieldname, value
		)

		with (
			patch.object(
				finishing_plan.frappe,
				"get_all",
				side_effect=[["FP-SOURCE"], ["FP-DEST"]],
			),
			patch.object(
				finishing_plan.frappe,
				"get_doc",
				side_effect=[source, destination],
			),
		):
			finishing_plan.remove_old_lot_transfer_tracking("LT-CANCEL")

		self.assertEqual(
			[row.lot_transfer for row in source.finishing_old_lot_given_items],
			["LT-KEEP"],
		)
		self.assertEqual(destination.finishing_old_lot_received_items, [])
		source.save.assert_called_once_with(ignore_permissions=True)
		destination.save.assert_called_once_with(ignore_permissions=True)

	def test_old_lot_source_balance_subtracts_quantities_already_given(self):
		source = frappe._dict(
			finishing_plan_details=[
				frappe._dict(
					item_variant="VARIANT-S",
					return_qty=5,
					pack_return_qty=4,
				),
			],
			finishing_old_lot_given_items=[
				frappe._dict(
					item_variant="VARIANT-S",
					loose_piece_given=2,
					loose_piece_set_given=1,
					lot_transfer=None,
				),
			],
		)

		balance = finishing_plan._get_old_lot_source_balance(source, "VARIANT-S")

		self.assertEqual(balance, (3, 3))

	def test_destination_receipts_are_derived_from_source_side_history(self):
		destination = frappe._dict(
			name="FP-DEST",
			finishing_old_lot_received_items=[],
		)
		given_row = frappe._dict(
			source_fp="FP-SOURCE",
			item_variant="VARIANT-S",
			colour="Blue",
			part=None,
			set_combination='{"major_colour": "Blue"}',
			size="S",
			loose_piece_given=2,
			loose_piece_set_given=1,
			lot_transfer=None,
		)

		with patch.object(
			finishing_plan.frappe,
			"get_all",
			side_effect=[
				[given_row],
				[frappe._dict(name="FP-SOURCE", lot="LOT-SOURCE")],
			],
		):
			received = finishing_plan._get_old_lot_received_rows(destination)

		self.assertEqual(len(received), 1)
		self.assertEqual(received[0].source_fp, "FP-SOURCE")
		self.assertEqual(received[0].source_lot, "LOT-SOURCE")
		self.assertEqual(received[0].loose_piece_taken, 2)
		self.assertEqual(received[0].loose_piece_set_taken, 1)

	def test_old_lot_transfer_stores_only_source_side_history(self):
		source = MagicMock()
		lot_transfer = MagicMock(name="LT-TEST")
		lot_transfer.name = "LT-TEST"
		variant = frappe._dict(
			item="ITEM-1",
			attributes=[frappe._dict(attribute="Size", attribute_value="S")],
		)

		def get_doc(doctype, name):
			if doctype == "Finishing Plan" and name == "FP-SOURCE":
				return source
			if doctype == "Item Variant":
				return variant
			raise AssertionError((doctype, name))

		data = [{
			"source_fp": "FP-SOURCE",
			"lot": "LOT-SOURCE",
			"warehouse": "WH-1",
			"old_lot_inward": {
				"data": {
					"Blue": {
						"part": None,
						"set_combination": "Blue",
						"values": {
							"S": {
								"transfer_loose_piece": 1,
								"transfer_loose_piece_set": 0,
							},
						},
					},
				},
			},
		}]

		with (
			patch.object(
				finishing_plan.frappe,
				"get_value",
				side_effect=[
					("Size", "Colour", 0, None, None, None),
					"Nos",
				],
			),
			patch.object(finishing_plan.frappe.db, "get_single_value", return_value="Purchase"),
			patch.object(finishing_plan.frappe, "get_doc", side_effect=get_doc),
			patch.object(finishing_plan.frappe, "new_doc", return_value=lot_transfer),
			patch.object(finishing_plan.frappe.db, "commit"),
			patch.object(finishing_plan, "build_variant_attributes", return_value={}),
			patch.object(finishing_plan, "get_or_create_variant", return_value="VARIANT-S"),
			patch.object(
				finishing_plan,
				"get_attribute_details",
				return_value={
					"attributes": [],
					"primary_attribute": "Size",
					"primary_attribute_values": ["S"],
					"default_uom": "Nos",
					"secondary_uom": None,
				},
			),
			patch.object(finishing_plan, "get_item_attribute_details", return_value={}),
			patch.object(finishing_plan, "get_item_group_index", return_value=-1),
			patch.object(finishing_plan, "_validate_old_lot_transfer_balances"),
		):
			finishing_plan.create_lot_transfer(
				data, "ITEM-1", "IPD-1", "LOT-DEST", "FP-DEST"
			)

		lot_transfer.submit.assert_called_once_with()
		source.append.assert_called_once()
		fieldname, row = source.append.call_args.args
		self.assertEqual(fieldname, "finishing_old_lot_given_items")
		self.assertEqual(row["destination_fp"], "FP-DEST")
		self.assertEqual(row["loose_piece_given"], 1)
		source.save.assert_called_once_with(ignore_permissions=True)

	def test_packing_quantities_are_rebuilt_after_fractional_grn_cancellation(self):
		doc = frappe.get_doc({
			"doctype": "Finishing Plan",
			"work_order": "WO-TEST",
			"lot": "LOT-TEST",
			"production_detail": "IPD-TEST",
			"finishing_plan_grn_details": [
				{"item_variant": "VARIANT-2T", "quantity": -0.333333333, "dispatched": 0},
				{"item_variant": "VARIANT-3T", "quantity": -0.333333333, "dispatched": 0},
			],
		})

		with patch.object(finishing_plan.frappe, "get_all", return_value=[]):
			finishing_plan.rebuild_finishing_packing_quantities(doc)

		self.assertEqual(
			[row.quantity for row in doc.finishing_plan_grn_details],
			[0, 0],
		)

	def test_migrated_legacy_boxes_and_dynamic_grn_rebuild_as_pieces(self):
		doc = frappe.get_doc({
			"doctype": "Finishing Plan",
			"work_order": "WO-TEST",
			"lot": "LOT-TEST",
			"production_detail": "IPD-TEST",
			"finishing_plan_grn_details": [
				{"item_variant": "VARIANT-S", "quantity": 15, "dispatched": 0},
			],
		})
		grns = [
			frappe._dict(
				name="GRN-LEGACY",
				packing_calculation_version=1,
				total_packing_boxes=60,
				total_packing_pieces=720,
			),
			frappe._dict(
				name="GRN-DYNAMIC",
				packing_calculation_version=2,
				total_packing_boxes=2,
				total_packing_pieces=10,
			),
		]
		items = {
			"GRN-LEGACY": [frappe._dict(item_variant="VARIANT-S", quantity=15)],
			"GRN-DYNAMIC": [frappe._dict(item_variant="VARIANT-S", quantity=10)],
		}

		def get_all(doctype, filters=None, **_kwargs):
			if doctype == "Goods Received Note":
				return grns
			if doctype == "Goods Received Note Item":
				return items[filters["parent"]]
			if doctype == "GRN Packing Batch":
				return []
			raise AssertionError(doctype)

		with (
			patch.object(finishing_plan.frappe, "get_all", side_effect=get_all),
			patch.object(finishing_plan.frappe, "get_cached_value", return_value="Size"),
			patch.object(finishing_plan, "get_variant_attr_details", return_value={"Size": "S"}),
		):
			finishing_plan.rebuild_finishing_packing_quantities(doc)

		self.assertEqual(doc.finishing_plan_grn_details[0].quantity, 190)

	def _source_lot(self):
		lot = SimpleNamespace(
			name="LOT-SOURCE",
			production_detail="IPD-SOURCE",
			item="SOURCE-ITEM",
			lot_order_details=[
				frappe._dict(
					item_variant="NAVY-S", quantity=10, cut_qty=12,
					set_combination={"major_colour": "Navy"},
				),
				frappe._dict(
					item_variant="RED-S", quantity=5, cut_qty=5,
					set_combination={"major_colour": "Red"},
				),
				frappe._dict(
					item_variant="NAVY-M", quantity=20, cut_qty=20,
					set_combination={"major_colour": "Navy"},
				),
			],
			items=[
				frappe._dict(item_variant="SIZE-S", qty=3),
				frappe._dict(item_variant="SIZE-M", qty=4),
			],
		)
		lot.save = MagicMock()
		return lot

	def _variant_attributes(self, variant):
		return {
			"NAVY-S": {"Colour": "Navy", "Size": "S"},
			"RED-S": {"Colour": "Red", "Size": "S"},
			"NAVY-M": {"Colour": "Navy", "Size": "M"},
			"SIZE-S": {"Size": "S"},
			"SIZE-M": {"Size": "M"},
		}[variant]

	def test_alternative_conversion_reduces_source_lot_and_rebuilds_totals(self):
		lot = self._source_lot()
		with (
			patch.object(finishing_plan.frappe.db, "sql"),
			patch.object(finishing_plan.frappe, "get_doc", return_value=lot),
			patch.object(
				finishing_plan.frappe,
				"get_value",
				return_value=(5, "Size", "Colour"),
			),
			patch.object(
				finishing_plan,
				"get_variant_attr_details",
				side_effect=self._variant_attributes,
			),
		):
			finishing_plan._reduce_source_lot_quantity(
				"LOT-SOURCE",
				[
					{"colour": "Navy", "size": "S", "qty": 3},
					{"colour": "Navy", "size": "M", "qty": 5},
				],
			)

		self.assertEqual(
			[row.quantity for row in lot.lot_order_details],
			[7, 5, 15],
		)
		self.assertEqual(
			[row.cut_qty for row in lot.lot_order_details],
			[12, 5, 20],
		)
		self.assertEqual([row.qty for row in lot.items], [2.4, 3])
		self.assertEqual(lot.total_order_quantity, 27)
		self.assertEqual(lot.total_quantity, 5.4)
		lot.save.assert_called_once_with(ignore_permissions=True)

	def test_source_lot_planned_quantity_clamps_at_zero_for_excess_cutting(self):
		lot = self._source_lot()
		with (
			patch.object(finishing_plan.frappe.db, "sql"),
			patch.object(finishing_plan.frappe, "get_doc", return_value=lot),
			patch.object(
				finishing_plan.frappe,
				"get_value",
				return_value=(5, "Size", "Colour"),
			),
			patch.object(
				finishing_plan,
				"get_variant_attr_details",
				side_effect=self._variant_attributes,
			),
		):
			finishing_plan._reduce_source_lot_quantity(
				"LOT-SOURCE",
				[{"colour": "Navy", "size": "S", "qty": 12}],
			)

		self.assertEqual(
			[row.quantity for row in lot.lot_order_details],
			[0, 5, 20],
		)
		self.assertEqual(
			[row.cut_qty for row in lot.lot_order_details],
			[12, 5, 20],
		)
		self.assertEqual([row.qty for row in lot.items], [1, 4])
		self.assertEqual(lot.total_order_quantity, 25)
		self.assertEqual(lot.total_quantity, 5)
		lot.save.assert_called_once_with(ignore_permissions=True)

	def test_excess_transfer_uses_full_quantity_and_stops_when_stock_issue_fails(self):
		source_fp = frappe._dict(
			item="SOURCE-ITEM",
			lot="LOT-SOURCE",
			finishing_plan_details=[],
		)
		source_fp.set = MagicMock()
		source_fp.save = MagicMock()
		wo_doc = frappe._dict(
			item="TARGET-ITEM",
			lot="LOT-TARGET",
			supplier="SUPPLIER-1",
		)
		fp_key = (
			"SOURCE-VARIANT-S",
			(("major_colour", "Navy"),),
		)
		fp_dict = {fp_key: {"transferred_qty": 0}}

		def get_value(doctype, name, fieldname):
			if doctype == "Item":
				return "Pieces"
			if doctype == "Item Variant":
				return "TARGET-ITEM"
			raise AssertionError((doctype, name, fieldname))

		stock_error = frappe.ValidationError("Insufficient source stock")
		with (
			patch.object(
				finishing_plan.frappe.db,
				"get_single_value",
				return_value="Accepted",
			),
			patch.object(finishing_plan.frappe, "get_value", side_effect=get_value),
			patch.object(finishing_plan, "get_finishing_plan_dict", return_value=fp_dict),
			patch.object(
				finishing_plan,
				"get_variant_attr_details",
				return_value={"Colour": "Navy", "Size": "S"},
			),
			patch.object(
				finishing_plan,
				"get_or_create_variant",
				return_value="SOURCE-VARIANT-S",
			),
			patch(
				"production_api.mrp_stock.doctype.stock_summary.stock_summary.create_bulk_stock_entry",
				side_effect=stock_error,
			) as create_stock,
		):
			with self.assertRaisesRegex(
				frappe.ValidationError,
				"Insufficient source stock",
			):
				finishing_plan._apply_transfer_delta(
					source_fp,
					wo_doc,
					[{
						"item_variant": "TARGET-VARIANT-S",
						"set_combination": {"major_colour": "Navy"},
						"qty": 120,
					}],
				)

		issue_items = create_stock.call_args.args[1]
		self.assertEqual(issue_items[0]["bal_qty"], 120)
		self.assertEqual(create_stock.call_args.args[2], "Material Issue")
		self.assertEqual(fp_dict[fp_key]["transferred_qty"], 120)
		source_fp.set.assert_not_called()
		source_fp.save.assert_not_called()
