from unittest import TestCase
from unittest.mock import MagicMock, patch

from frappe import _dict

from production_api import lot_pricing


class TestLotPricing(TestCase):
	def get_ppo(self):
		return _dict(doctype="Production Order", name="PPO-TEST", item="ITEM", lot_price_overrides=[])

	def test_unprinted_lot_uses_override_then_ppo_default(self):
		ppo = self.get_ppo()
		frappe_mock = MagicMock()
		frappe_mock.db.get_value.return_value = "PPO-TEST"
		frappe_mock.get_doc.return_value = ppo
		with (
			patch.object(lot_pricing, "frappe", frappe_mock),
			patch.object(lot_pricing, "get_production_order_price_map", return_value={"S": 100, "M": 110}),
			patch.object(lot_pricing, "get_lot_override_map", return_value={"LOT-1": {"M": 125}}),
			patch.object(lot_pricing, "get_lot_print_state", return_value={"locked": False, "documents": [], "prices": {}}),
		):
			pricing = lot_pricing.get_lot_pricing("LOT-1", "PPO-TEST")

		self.assertEqual(pricing["prices"]["S"]["effective_mrp"], 100)
		self.assertEqual(pricing["prices"]["M"]["effective_mrp"], 125)
		self.assertFalse(pricing["prices"]["S"]["has_override"])
		self.assertTrue(pricing["prices"]["M"]["has_override"])

	def test_printed_lot_keeps_box_sticker_snapshot_after_default_changes(self):
		ppo = self.get_ppo()
		frappe_mock = MagicMock()
		frappe_mock.db.get_value.return_value = "PPO-TEST"
		frappe_mock.get_doc.return_value = ppo
		print_state = {
			"locked": True,
			"documents": ["BSP-1"],
			"prices": {
				"S": {"snapshot_mrp": 100, "printed_quantity": 10, "printed_mrps": [100]},
				"M": {"snapshot_mrp": 110, "printed_quantity": 0, "printed_mrps": []},
			},
		}
		with (
			patch.object(lot_pricing, "frappe", frappe_mock),
			patch.object(lot_pricing, "get_production_order_price_map", return_value={"S": 150, "M": 160}),
			patch.object(lot_pricing, "get_lot_override_map", return_value={}),
			patch.object(lot_pricing, "get_lot_print_state", return_value=print_state),
		):
			pricing = lot_pricing.get_lot_pricing("LOT-1", "PPO-TEST")

		self.assertTrue(pricing["locked"])
		self.assertEqual(pricing["prices"]["S"]["effective_mrp"], 100)
		self.assertEqual(pricing["prices"]["M"]["effective_mrp"], 110)

	def test_unprinted_submitted_sticker_rows_are_synchronized(self):
		pricing = {
			"locked": False,
			"box_sticker_prints": ["BSP-1"],
			"prices": {"S": {"effective_mrp": 125}},
		}
		rows = [_dict(name="ROW-1", size="S", mrp=100)]
		frappe_mock = MagicMock()
		frappe_mock.get_all.return_value = rows
		with (
			patch.object(lot_pricing, "get_lot_pricing", return_value=pricing),
			patch.object(lot_pricing, "frappe", frappe_mock),
		):
			updated = lot_pricing.sync_unprinted_box_sticker_prices("LOT-1", "PPO-TEST")

		self.assertEqual(updated, 1)
		frappe_mock.db.set_value.assert_called_once_with(
			"Box Sticker Print Detail", "ROW-1", "mrp", 125.0, update_modified=False
		)

	def test_printed_lot_sticker_rows_are_not_synchronized(self):
		pricing = {"locked": True, "box_sticker_prints": ["BSP-1"], "prices": {}}
		frappe_mock = MagicMock()
		with (
			patch.object(lot_pricing, "get_lot_pricing", return_value=pricing),
			patch.object(lot_pricing, "frappe", frappe_mock),
		):
			updated = lot_pricing.sync_unprinted_box_sticker_prices("LOT-1", "PPO-TEST")

		self.assertEqual(updated, 0)
		frappe_mock.get_all.assert_not_called()
