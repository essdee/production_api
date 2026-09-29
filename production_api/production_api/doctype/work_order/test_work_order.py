# Copyright (c) 2024, Essdee and Contributors
# See license.txt

from unittest import TestCase
from unittest.mock import patch, MagicMock

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.work_order import work_order as work_order_module
from production_api.production_api.doctype.work_order.work_order import create_finishing_detail


class TestWorkOrderPricing(TestCase):
	def test_packing_requires_explicit_price_for_each_used_lot_size(self):
		work_order = MagicMock()
		work_order.lot = "LOT-TEST"
		work_order.item = "ITEM-TEST"
		work_order.work_order_calculated_items = [
			frappe._dict(item_variant="ITEM-S", quantity=10),
			frappe._dict(item_variant="ITEM-M", quantity=12),
		]

		def get_value(doctype, name, fieldname):
			if doctype == "Lot":
				return "PPO-TEST"
			if doctype == "Production Order":
				return 0
			if doctype == "Item":
				return "Size"
			return None
		frappe_mock = MagicMock()
		frappe_mock.db.get_value.side_effect = get_value
		frappe_mock.get_value.side_effect = get_value

		with (
			patch.object(work_order_module, "frappe", frappe_mock),
			patch.object(
				work_order_module,
				"get_variant_attr_details",
				side_effect=lambda item: {"Size": item.removeprefix("ITEM-")},
			),
			patch(
				"production_api.lot_pricing.get_explicit_lot_price_map",
				return_value={"M": 125},
			),
		):
			missing = work_order_module.WorkOrder.get_missing_box_sticker_prices(work_order)

		self.assertEqual(missing, ["S"])

	def test_packing_price_validation_locks_ppo_and_blocks_missing_prices(self):
		work_order = MagicMock()
		work_order.includes_packing = 1
		work_order.lot = "LOT-TEST"
		work_order.get_missing_box_sticker_prices.return_value = ["S", "M"]

		def get_value(doctype, name, fieldname):
			if doctype == "Lot":
				return "PPO-TEST"
			if doctype == "Production Order":
				return 0
			return None
		frappe_mock = MagicMock()
		frappe_mock.db.get_value.side_effect = get_value
		frappe_mock.throw.side_effect = frappe.ValidationError

		with (
			patch.object(work_order_module, "frappe", frappe_mock),
			patch(
				"production_api.production_api.doctype.production_order.production_order.lock_production_orders"
			) as lock_production_orders,
			self.assertRaises(frappe.ValidationError),
		):
			work_order_module.WorkOrder.validate_packing_lot_prices(work_order)

		lock_production_orders.assert_called_once_with("PPO-TEST")
		work_order.get_missing_box_sticker_prices.assert_called_once_with(for_update=True)


class TestWorkOrder(FrappeTestCase):
	def test_create_finishing_detail_skips_when_existing_fp_present(self):
		"""Guard should short-circuit if a non-cancelled Finishing Plan already
		exists for the Work Order. No new FP should be saved."""
		fake_wo = "WO-TEST-DUP-0001"
		existing_fp = "FP-EXISTING-0001"

		with patch.object(
			work_order_module.frappe, "get_all", return_value=[existing_fp]
		) as mock_get_all, patch.object(
			work_order_module.frappe, "get_doc"
		) as mock_get_doc, patch.object(
			work_order_module.frappe, "new_doc"
		) as mock_new_doc:
			result = create_finishing_detail(fake_wo)

		self.assertEqual(result, existing_fp)
		mock_get_all.assert_called_once_with(
			"Finishing Plan",
			filters={"work_order": fake_wo, "docstatus": ["<", 2]},
			pluck="name",
			limit=1,
		)
		# The guard must return before any WO fetch or FP construction.
		mock_get_doc.assert_not_called()
		mock_new_doc.assert_not_called()

	def test_create_finishing_detail_proceeds_when_no_existing_fp(self):
		"""If no FP exists for this WO, the function must proceed past the guard
		(i.e. fetch the Work Order doc). We only assert that it moves past the
		short-circuit; the full creation pipeline is out of scope for this test."""
		fake_wo = "WO-TEST-NEW-0002"

		wo_doc_mock = MagicMock()
		wo_doc_mock.work_order_calculated_items = []

		with patch.object(
			work_order_module.frappe, "get_all", return_value=[]
		), patch.object(
			work_order_module.frappe, "get_doc", return_value=wo_doc_mock
		) as mock_get_doc, patch.object(
			work_order_module.frappe.db, "get_single_value", return_value=None
		):
			# The downstream code will raise once it hits unmocked territory;
			# we only need to prove the guard let execution pass.
			try:
				create_finishing_detail(fake_wo)
			except Exception:
				pass

		mock_get_doc.assert_any_call("Work Order", fake_wo)

	def test_create_finishing_detail_treats_cancelled_fp_as_absent(self):
		"""A cancelled FP (docstatus == 2) must NOT block creation. The guard
		query excludes docstatus >= 2, so frappe.get_all returns []."""
		fake_wo = "WO-TEST-CANCELLED-0003"

		with patch.object(
			work_order_module.frappe, "get_all", return_value=[]
		) as mock_get_all, patch.object(
			work_order_module.frappe, "get_doc"
		), patch.object(
			work_order_module.frappe.db, "get_single_value", return_value=None
		):
			try:
				create_finishing_detail(fake_wo)
			except Exception:
				pass

		# Confirm the filter excludes cancelled docs (docstatus < 2).
		call_kwargs = mock_get_all.call_args.kwargs
		self.assertEqual(call_kwargs["filters"]["docstatus"], ["<", 2])
