from types import SimpleNamespace
from unittest import TestCase

from production_api.api.ppo_report import (
	_empty_snapshot,
	_inward_quantity_in_boxes,
	_validate_filters,
	build_production_snapshot,
)


def row(**kwargs):
	return SimpleNamespace(
		**kwargs,
		get=lambda key, default=None: kwargs.get(key, default),
	)


class TestPPOReportSnapshot(TestCase):
	def test_direct_ppo_does_not_require_delivery_dates(self):
		result = _validate_filters(
			item="GYM VEST",
			ppo="PPO-1",
			ppo_start_date=None,
			ppo_end_date=None,
			inward_start_date="2026-07-01",
			inward_end_date="2026-07-31",
		)

		self.assertEqual(result["ppo"], "PPO-1")
		self.assertIsNone(result["ppo_start_date"])

	def test_preserves_an_optional_lot_filter(self):
		result = _validate_filters(
			item="GYM VEST",
			ppo="PPO-1",
			lot="LOT-1",
			ppo_start_date=None,
			ppo_end_date=None,
			inward_start_date="2026-07-01",
			inward_end_date="2026-07-31",
		)

		self.assertEqual(result["lot"], "LOT-1")

	def test_empty_snapshot_explains_missing_delivery_range(self):
		result = _empty_snapshot(
			{
				"item": "GYM VEST",
				"ppo_start_date": "2026-07-01",
				"ppo_end_date": "2026-07-31",
			},
			[],
		)

		self.assertEqual(
			result["empty_state"]["code"],
			"no_ppo_for_delivery_range",
		)
		self.assertIn("GYM VEST", result["empty_state"]["message"])
		self.assertIn("2026-07-01", result["empty_state"]["message"])

	def test_handles_multiple_lots_and_mismatched_inward_items(self):
		result = build_production_snapshot(
			filters={
				"item": "GYM VEST",
				"ppo_start_date": "2026-07-01",
				"ppo_end_date": "2026-07-31",
				"inward_start_date": "2026-07-01",
				"inward_end_date": "2026-07-31",
			},
			ppo_rows=[
				row(
					name="PPO-1",
					item="GYM VEST",
					delivery_date="2026-07-15",
					item_variant="GYM VEST-S",
					quantity=200,
				)
			],
			lot_rows=[
				row(
					lot="LOT-1",
					production_order="PPO-1",
					lot_item="GYM VEST",
					status="Open",
					is_transferred=0,
					transferred_lot=None,
					item="GYM VEST",
					item_variant="GYM VEST-S",
					planned_quantity=120,
				),
				row(
					lot="LOT-2",
					production_order="PPO-1",
					lot_item="JUNIOR GYM VEST",
					status="Open",
					is_transferred=0,
					transferred_lot=None,
					item="JUNIOR GYM VEST",
					item_variant="JUNIOR GYM VEST-S",
					planned_quantity=80,
				),
			],
			inward_rows=[
				row(
					lot="LOT-1",
					item="GYM VEST",
					item_variant="GYM VEST-S",
					inward_quantity=100,
					uom="Box",
					stock_entry="FG-1",
					posting_date="2026-07-20",
					warehouse="FG",
				),
				row(
					lot="LOT-1",
					item="OTHER VEST",
					item_variant="OTHER VEST-S",
					inward_quantity=5,
					uom="Box",
					stock_entry="FG-2",
					posting_date="2026-07-21",
					warehouse="FG",
				),
			],
			stock={
				"GYM VEST-S": {"bal_qty": 10, "uom": "Box"},
				"JUNIOR GYM VEST-S": {"bal_qty": 20, "uom": "Box"},
			},
			warehouses=["FG"],
			variant_attributes={
				"GYM VEST-S": "S",
				"JUNIOR GYM VEST-S": "S",
				"OTHER VEST-S": "S",
			},
			column_order=["S", "M", "L", "XL"],
		)

		self.assertEqual(result["summary"]["ppo_quantity"], 200)
		self.assertEqual(result["summary"]["lot_quantity"], 200)
		self.assertEqual(result["summary"]["inward_quantity"], 105)
		self.assertEqual(result["summary"]["wip_quantity"], 95)
		self.assertEqual(result["summary"]["over_inward_quantity"], 0)
		self.assertEqual(result["ppos"][0]["lot_count"], 2)
		self.assertEqual(
			result["ppos"][0]["details"][0]["primary_attribute_value"],
			"S",
		)
		self.assertEqual(result["column_order"], ["S", "M", "L", "XL"])

		lot_one = next(lot for lot in result["lots"] if lot["name"] == "LOT-1")
		self.assertEqual(lot_one["size_rows"][0]["planned_quantity"], 120)
		self.assertEqual(lot_one["size_rows"][0]["inward_quantity"], 105)
		self.assertEqual(lot_one["size_rows"][0]["wip_quantity"], 15)

	def test_subtracts_transferred_lot_quantities_by_size(self):
		result = build_production_snapshot(
			filters={"item": "GYM VEST"},
			ppo_rows=[
				row(
					name="PPO-1",
					item="GYM VEST",
					delivery_date="2026-07-15",
					item_variant="GYM VEST-S",
					quantity=200,
				)
			],
			lot_rows=[
				row(
					lot="LOT-1",
					production_order="PPO-1",
					lot_item="GYM VEST",
					status="Open",
					has_transferred=1,
					is_transferred=0,
					transferred_lot=None,
					item="GYM VEST",
					item_variant="GYM VEST-S",
					planned_quantity=120,
				)
			],
			transferred_lot_rows=[
				row(
					source_lot="LOT-1",
					transferred_lot="ALT-LOT-1",
					item_variant="OTHER VEST-S",
					transferred_quantity=30,
				)
			],
			inward_rows=[
				row(
					lot="LOT-1",
					item="OTHER VEST",
					item_variant="OTHER VEST-S",
					inward_quantity=20,
					uom="Box",
					stock_entry="FG-1",
					posting_date="2026-07-20",
					warehouse="FG",
				)
			],
			stock={},
			warehouses=[],
			variant_attributes={
				"GYM VEST-S": "S",
				"OTHER VEST-S": "S",
			},
			column_order=["S"],
		)

		ppo = result["ppos"][0]
		lot = result["lots"][0]
		self.assertEqual(ppo["original_quantity"], 200)
		self.assertEqual(ppo["transferred_quantity"], 30)
		self.assertEqual(ppo["quantity"], 170)
		self.assertEqual(lot["original_planned_quantity"], 120)
		self.assertEqual(lot["transferred_quantity"], 30)
		self.assertEqual(lot["planned_quantity"], 90)
		self.assertEqual(lot["inward_quantity"], 20)
		self.assertEqual(lot["wip_quantity"], 70)
		self.assertEqual(lot["transferred_lots"], ["ALT-LOT-1"])

	def test_returns_zero_wip_when_inward_exceeds_plan(self):
		result = build_production_snapshot(
			filters={"item": "ITEM"},
			ppo_rows=[],
			lot_rows=[
				row(
					lot="LOT-1",
					production_order=None,
					lot_item="ITEM",
					status="Open",
					is_transferred=0,
					transferred_lot=None,
					item="ITEM",
					item_variant="ITEM-A",
					planned_quantity=10,
				)
			],
			inward_rows=[
				row(
					lot="LOT-1",
					item="ITEM",
					item_variant="ITEM-A",
					inward_quantity=12,
					uom="Box",
					stock_entry="FG-1",
					posting_date="2026-07-20",
					warehouse="FG",
				)
			],
			stock={},
			warehouses=[],
		)

		item = result["lots"][0]["items"][0]
		self.assertEqual(item["wip_quantity"], 0)
		self.assertEqual(item["over_inward_quantity"], 2)

	def test_converts_piece_inward_to_boxes(self):
		quantity, warning = _inward_quantity_in_boxes(
			row(
				item_variant="ITEM-A",
				inward_quantity=25,
				uom="Pieces",
				stock_qty=25,
				stock_uom="Pieces",
				conversion_factor=1,
				box_conversion_factor=5,
			)
		)

		self.assertEqual(quantity, 5)
		self.assertIsNone(warning)

	def test_excludes_inward_when_box_conversion_is_missing(self):
		result = build_production_snapshot(
			filters={"item": "ITEM"},
			ppo_rows=[],
			lot_rows=[
				row(
					lot="LOT-1",
					production_order=None,
					lot_item="ITEM",
					status="Open",
					is_transferred=0,
					transferred_lot=None,
					item="ITEM",
					item_variant="ITEM-A",
					planned_quantity=10,
				)
			],
			inward_rows=[
				row(
					lot="LOT-1",
					item="ITEM",
					item_variant="ITEM-A",
					inward_quantity=25,
					uom="Pieces",
					stock_qty=25,
					stock_uom="Pieces",
					conversion_factor=1,
					box_conversion_factor=None,
					stock_entry="FG-1",
					posting_date="2026-07-20",
					warehouse="FG",
				)
			],
			stock={},
			warehouses=[],
		)

		item = result["lots"][0]["items"][0]
		self.assertEqual(item["inward_quantity"], 0)
		self.assertEqual(item["wip_quantity"], 10)
		self.assertEqual(len(result["warnings"]), 1)
		self.assertIn("Pieces to Box", result["warnings"][0])
