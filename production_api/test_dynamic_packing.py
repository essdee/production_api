from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.dynamic_packing import aggregate_batch_pieces, normalize_packing_batches
from production_api.production_api.doctype.work_order import work_order


class TestDynamicPacking(FrappeTestCase):
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
