# Copyright (c) 2024, Essdee and Contributors
# See license.txt

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from frappe import _dict

from production_api.essdee_production.doctype.box_sticker_print import box_sticker_print
from production_api.production_api.doctype.work_order.work_order import build_box_sticker_details


class TestBoxStickerPrint(TestCase):
	def test_save_does_not_refetch_or_overwrite_mrp(self):
		doc = SimpleNamespace(
			box_sticker_print_details=[
				_dict(size="S", quantity=1, allow_excess_quantity=0, mrp=999)
			],
		)
		frappe_mock = MagicMock()

		with patch.object(box_sticker_print, "frappe", frappe_mock):
			box_sticker_print.BoxStickerPrint.before_validate(doc)

		self.assertEqual(doc.box_sticker_print_details[0].mrp, 999)
		frappe_mock.db.get_value.assert_not_called()

	def test_manual_form_uses_fg_item_prices_not_linked_lot_prices(self):
		frappe_mock = MagicMock()
		frappe_mock.get_value.return_value = ("S,M", "100,110")

		with patch.object(box_sticker_print, "frappe", frappe_mock):
			details = box_sticker_print.get_fg_details.__wrapped__("FG-1", lot="LOT-1")

		self.assertEqual(details, [{"size": "S", "mrp": "100"}, {"size": "M", "mrp": "110"}])
		frappe_mock.db.get_value.assert_not_called()

	def test_manual_form_falls_back_to_latest_sticker_prices(self):
		previous = SimpleNamespace(
			box_sticker_print_details=[_dict(size="S", mrp=95), _dict(size="M", mrp=105)]
		)
		frappe_mock = MagicMock()
		frappe_mock.get_value.return_value = ("S,M", "")
		frappe_mock.get_list.return_value = ["BSP-OLD"]
		frappe_mock.get_doc.return_value = previous

		with patch.object(box_sticker_print, "frappe", frappe_mock):
			details = box_sticker_print.get_fg_details.__wrapped__("FG-1", lot="LOT-1")

		self.assertEqual(details, [{"size": "S", "mrp": 95}, {"size": "M", "mrp": 105}])

	def test_work_order_builds_sticker_rows_from_ppo_price_map(self):
		details = build_box_sticker_details(
			["S", "M"], {"S": 100, "M": 0}, {"S": 125, "M": 135}
		)

		self.assertEqual(
			details,
			[
				{
					"size": "S",
					"quantity": 100.0,
					"mrp": 125.0,
					"allow_excess_quantity": 0,
					"allow_excess_percentage": 5,
				},
				{
					"size": "M",
					"quantity": 0.0,
					"mrp": 135.0,
					"allow_excess_quantity": 1,
					"allow_excess_percentage": 5,
				},
			],
		)
