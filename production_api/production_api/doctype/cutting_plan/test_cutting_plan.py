# Copyright (c) 2024, Essdee and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.cutting_plan import cutting_plan


class TestCuttingPlan(FrappeTestCase):
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
