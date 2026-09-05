# Copyright (c) 2024, Essdee and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.cutting_plan import cutting_plan


class TestCuttingPlan(FrappeTestCase):
	def test_generate_refreshes_submitted_plan_from_latest_lot_data(self):
		cutting_plan_doc = MagicMock()
		cutting_plan_doc.name = "CP-TEST"
		cutting_plan_doc.docstatus = 1
		cutting_plan_doc.lot = "LOT-TEST"
		cutting_plan_doc.production_detail = "IPD-TEST"
		cutting_plan_doc.item = "GARMENT"
		cutting_plan_doc.items = []
		cutting_plan_doc.cutting_plan_cloth_details = []
		cutting_plan_doc.cutting_plan_accessory_details = []

		def set_rows(fieldname, rows):
			setattr(
				cutting_plan_doc,
				fieldname,
				[frappe._dict(row) if isinstance(row, dict) else row for row in rows],
			)

		cutting_plan_doc.set.side_effect = set_rows
		lot_doc = frappe._dict(lot_order_details=[frappe._dict(name="LOT-ROW-1")])
		ipd_doc = frappe._dict(
			packing_attribute="Colour",
			cloth_detail=[frappe._dict(name1="Body", cloth="FABRIC")],
		)
		variant_doc = frappe._dict(
			attributes=[frappe._dict(attribute="Colour", attribute_value="Red")]
		)
		latest_item_details = [{"items": [{"values": {"M": {"qty": 18}}}]}]
		saved_items = [
			frappe._dict(
				item_variant="GARMENT-RED-M",
				quantity=18,
				set_combination={},
			)
		]
		completed = {"items": [], "source": "latest-lot"}
		incomplete = {"items": [], "source": "current-ipd"}

		def get_doc(doctype, name):
			if (doctype, name) == ("Cutting Plan", "CP-TEST"):
				return cutting_plan_doc
			if (doctype, name) == ("Lot", "LOT-TEST"):
				return lot_doc
			if (doctype, name) == ("Item Variant", "GARMENT-RED-M"):
				return variant_doc
			raise AssertionError((doctype, name))

		with (
			patch.object(cutting_plan.frappe, "get_doc", side_effect=get_doc),
			patch.object(cutting_plan.frappe, "get_cached_doc", return_value=ipd_doc),
			patch.object(
				cutting_plan,
				"fetch_order_item_details",
				return_value=latest_item_details,
			) as fetch_order_item_details,
			patch.object(
				cutting_plan, "save_item_details", return_value=saved_items
			) as save_item_details,
			patch.object(
				cutting_plan,
				"get_complete_incomplete_structure",
				return_value=(completed, incomplete),
			) as rebuild_progress,
			patch.object(
				cutting_plan,
				"get_attribute_details",
				return_value={"dependent_attribute": "Style"},
			),
			patch.object(cutting_plan, "get_cloth_combination", return_value={}),
			patch.object(cutting_plan, "get_stitching_combination", return_value={}),
			patch.object(
				cutting_plan,
				"calculate_cloth",
				return_value=[
					{
						"type": "cloth",
						"cloth_type": "Body",
						"colour": "Red",
						"dia": "24 Dia",
						"quantity": 7.25,
					}
				],
			),
			patch.object(
				cutting_plan,
				"get_or_create_variant",
				return_value="FABRIC-RED-24",
			),
		):
			cutting_plan.get_cloth1("CP-TEST")

		fetch_order_item_details.assert_called_once_with(
			lot_doc.lot_order_details, "IPD-TEST"
		)
		save_item_details.assert_called_once_with(latest_item_details)
		rebuild_progress.assert_called_once_with("IPD-TEST", latest_item_details)
		self.assertEqual(cutting_plan_doc.items[0].quantity, 18)
		self.assertEqual(cutting_plan_doc.completed_items_json, completed)
		self.assertEqual(cutting_plan_doc.incomplete_items_json, incomplete)
		self.assertEqual(
			cutting_plan_doc.cutting_plan_cloth_details[0].required_weight, 7.25
		)
		self.assertEqual(cutting_plan_doc.cutting_plan_cloth_details[0].weight, 0)
		cutting_plan_doc.save.assert_called_once_with()

	def test_balance_lot_transfer_uses_cloth_balance_and_cutting_supplier(self):
		cp_doc = frappe._dict(
			name="CP-TEST",
			docstatus=1,
			lot="LOT-OLD",
			work_order="WO-CUTTING",
			cutting_plan_cloth_details=[
				frappe._dict(cloth_item_variant="FABRIC-RED", balance_weight=12.3456),
				frappe._dict(cloth_item_variant="FABRIC-BLUE", balance_weight=0),
				frappe._dict(cloth_item_variant="RIB-RED", balance_weight=2.5),
			],
		)
		lot_transfer = MagicMock()
		lot_transfer.name = "LT-TEST"

		def get_cached_value(doctype, name, fieldname):
			if doctype == "Work Order":
				return "CUTTING-LOCATION"
			if doctype == "Item Variant":
				return {"FABRIC-RED": "FABRIC", "RIB-RED": "RIB"}[name]
			if doctype == "Item":
				return "Kg"
			raise AssertionError((doctype, name, fieldname))

		with (
			patch.object(cutting_plan.frappe, "get_doc", return_value=cp_doc),
			patch.object(cutting_plan.frappe.db, "exists", return_value=True),
			patch.object(cutting_plan.frappe, "get_cached_value", side_effect=get_cached_value),
			patch.object(
				cutting_plan.frappe.db,
				"get_single_value",
				return_value="Accepted",
			),
			patch.object(cutting_plan.frappe, "new_doc", return_value=lot_transfer),
		):
			result = cutting_plan.create_balance_lot_transfer("CP-TEST", "LOT-NEW")

		self.assertEqual(result, "LT-TEST")
		self.assertTrue(lot_transfer.flags.allow_from_cutting_plan)
		lot_transfer.save.assert_called_once_with()
		items = lot_transfer.set.call_args.args[1]
		self.assertEqual([item["item"] for item in items], ["FABRIC-RED", "RIB-RED"])
		self.assertEqual([item["qty"] for item in items], [12.346, 2.5])
		self.assertTrue(all(item["from_lot"] == "LOT-OLD" for item in items))
		self.assertTrue(all(item["to_lot"] == "LOT-NEW" for item in items))
		self.assertTrue(all(item["warehouse"] == "CUTTING-LOCATION" for item in items))
		self.assertTrue(all(item["uom"] == "Kg" for item in items))
