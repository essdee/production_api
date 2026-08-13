# Copyright (c) 2024, Essdee and Contributors
# See license.txt

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from frappe import _dict

from production_api.essdee_production.doctype.box_sticker_print import box_sticker_print


class TestBoxStickerPrint(TestCase):
	def test_manual_sticker_keeps_entered_mrp(self):
		doc = SimpleNamespace(
			against=None,
			against_id=None,
			lot="LOT-1",
			box_sticker_print_details=[_dict(size="S", mrp=999)],
		)
		frappe_mock = MagicMock()

		with patch.object(box_sticker_print, "frappe", frappe_mock):
			box_sticker_print.BoxStickerPrint.apply_linked_lot_prices(doc)

		self.assertEqual(doc.box_sticker_print_details[0].mrp, 999)
		frappe_mock.db.get_value.assert_not_called()

	def test_work_order_sticker_uses_linked_ppo_mrp(self):
		doc = SimpleNamespace(
			against="Work Order",
			against_id="WO-1",
			lot="LOT-1",
			box_sticker_print_details=[_dict(size="S", mrp=999)],
		)
		frappe_mock = MagicMock()
		frappe_mock.db.get_value.return_value = "PPO-1"

		with (
			patch.object(box_sticker_print, "frappe", frappe_mock),
			patch(
				"production_api.production_api.doctype.production_order.production_order.lock_production_orders"
			) as lock_production_orders,
			patch(
				"production_api.lot_pricing.get_effective_lot_price_map",
				return_value={"S": 125},
			),
		):
			box_sticker_print.BoxStickerPrint.apply_linked_lot_prices(doc)

		self.assertEqual(doc.box_sticker_print_details[0].mrp, 125)
		lock_production_orders.assert_called_once_with("PPO-1")

	def test_manual_form_uses_fg_item_prices_not_linked_lot_prices(self):
		frappe_mock = MagicMock()
		frappe_mock.get_value.return_value = ("S,M", "100,110")

		with patch.object(box_sticker_print, "frappe", frappe_mock):
			details = box_sticker_print.get_fg_details.__wrapped__("FG-1", lot="LOT-1")

		self.assertEqual(details, [{"size": "S", "mrp": "100"}, {"size": "M", "mrp": "110"}])
		frappe_mock.db.get_value.assert_not_called()
