from types import SimpleNamespace
from unittest import TestCase

from production_api.api.ppo_report import (
	_aggregate_production_stage,
	_empty_snapshot,
	_production_stage_from_work_orders,
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
			inward_start_date="2026-07-01",
			inward_end_date="2026-07-31",
		)

		self.assertEqual(result["ppo"], "PPO-1")
		self.assertNotIn("ppo_start_date", result)

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

	def test_empty_snapshot_explains_missing_open_ppo(self):
		result = _empty_snapshot(
			{"item": "GYM VEST"},
			[],
		)

		self.assertEqual(
			result["empty_state"]["code"],
			"no_open_ppo",
		)
		self.assertIn("GYM VEST", result["empty_state"]["message"])
		self.assertIn("open or pending", result["empty_state"]["message"])

	def test_derives_cutting_stitching_and_packing_stages(self):
		self.assertEqual(_production_stage_from_work_orders([], []), "Cutting")
		self.assertEqual(
			_production_stage_from_work_orders(["DC-1"], []),
			"Stitching",
		)
		self.assertEqual(
			_production_stage_from_work_orders(["DC-1"], ["GRN-1"]),
			"Packing",
		)
		self.assertEqual(
			_aggregate_production_stage(["Packing", "Cutting", "Stitching"]),
			"Cutting",
		)

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

	def test_wip_is_calculated_separately_for_each_ppo_linked_lots(self):
		result = build_production_snapshot(
			filters={"item": "GYM VEST"},
			ppo_rows=[
				row(
					name="PPO-1",
					item="GYM VEST",
					delivery_date="2026-07-01",
					item_variant="GYM VEST-S",
					quantity=60,
				),
				row(
					name="PPO-2",
					item="GYM VEST",
					delivery_date="2026-07-02",
					item_variant="GYM VEST-S",
					quantity=40,
				),
			],
			lot_rows=[
				row(
					lot="LOT-1",
					production_order="PPO-1",
					lot_item="GYM VEST",
					status="Open",
					has_transferred=0,
					is_transferred=0,
					transferred_lot=None,
					item="GYM VEST",
					item_variant="GYM VEST-S",
					planned_quantity=90,
				),
				row(
					lot="LOT-2",
					production_order="PPO-2",
					lot_item="GYM VEST",
					status="Open",
					has_transferred=0,
					is_transferred=0,
					transferred_lot=None,
					item="GYM VEST",
					item_variant="GYM VEST-S",
					planned_quantity=40,
				),
			],
			inward_rows=[
				row(
					lot="LOT-1",
					item="GYM VEST",
					item_variant="GYM VEST-S",
					inward_quantity=50,
					uom="Box",
					stock_entry="FG-1",
					posting_date="2026-07-10",
					warehouse="FG",
				),
				row(
					lot="LOT-2",
					item="OTHER VEST",
					item_variant="OTHER VEST-S",
					inward_quantity=5,
					uom="Box",
					stock_entry="FG-2",
					posting_date="2026-07-10",
					warehouse="FG",
				),
			],
			stock={},
			warehouses=[],
			variant_attributes={
				"GYM VEST-S": "S",
				"OTHER VEST-S": "S",
			},
			column_order=["S"],
		)

		self.assertEqual(result["summary"]["ppo_quantity"], 100)
		self.assertEqual(result["summary"]["inward_quantity"], 55)
		self.assertEqual(result["summary"]["wip_quantity"], 45)
		self.assertEqual(result["summary"]["over_inward_quantity"], 0)
		ppos = {ppo["name"]: ppo for ppo in result["ppos"]}
		self.assertEqual(ppos["PPO-1"]["inward_quantity"], 50)
		self.assertEqual(ppos["PPO-1"]["wip_quantity"], 10)
		self.assertEqual(ppos["PPO-2"]["inward_quantity"], 5)
		self.assertEqual(ppos["PPO-2"]["wip_quantity"], 35)

	def test_wip_uses_ppo_projection_instead_of_lot_plan(self):
		result = build_production_snapshot(
			filters={"item": "GYM VEST"},
			ppo_rows=[
				row(
					name="PPO-1",
					item="GYM VEST",
					delivery_date="2026-07-01",
					item_variant="GYM VEST-S",
					quantity=100,
				)
			],
			lot_rows=[
				row(
					lot="LOT-1",
					production_order="PPO-1",
					lot_item="GYM VEST",
					status="Open",
					has_transferred=0,
					is_transferred=0,
					transferred_lot=None,
					item="GYM VEST",
					item_variant="GYM VEST-S",
					planned_quantity=150,
				)
			],
			inward_rows=[
				row(
					lot="LOT-1",
					item="GYM VEST",
					item_variant="GYM VEST-S",
					inward_quantity=60,
					uom="Box",
					stock_entry="FG-1",
					posting_date="2026-07-10",
					warehouse="FG",
				)
			],
			stock={},
			warehouses=[],
			variant_attributes={"GYM VEST-S": "S"},
			column_order=["S"],
		)

		self.assertEqual(result["summary"]["ppo_quantity"], 100)
		self.assertEqual(result["summary"]["lot_quantity"], 150)
		self.assertEqual(result["summary"]["inward_quantity"], 60)
		self.assertEqual(result["summary"]["wip_quantity"], 40)
		self.assertEqual(result["ppos"][0]["wip_quantity"], 40)

	def test_size_surplus_offsets_another_size_shortfall_in_same_ppo(self):
		result = build_production_snapshot(
			filters={"item": "GYM VEST"},
			ppo_rows=[
				row(
					name="PPO-1",
					item="GYM VEST",
					delivery_date="2026-07-01",
					item_variant="GYM VEST-S",
					quantity=500,
				),
				row(
					name="PPO-1",
					item="GYM VEST",
					delivery_date="2026-07-01",
					item_variant="GYM VEST-M",
					quantity=400,
				),
			],
			lot_rows=[
				row(
					lot="LOT-1",
					production_order="PPO-1",
					lot_item="GYM VEST",
					status="Open",
					has_transferred=0,
					is_transferred=0,
					transferred_lot=None,
					item="GYM VEST",
					item_variant="GYM VEST-S",
					planned_quantity=500,
				),
				row(
					lot="LOT-1",
					production_order="PPO-1",
					lot_item="GYM VEST",
					status="Open",
					has_transferred=0,
					is_transferred=0,
					transferred_lot=None,
					item="GYM VEST",
					item_variant="GYM VEST-M",
					planned_quantity=400,
				),
			],
			inward_rows=[
				row(
					lot="LOT-1",
					item="GYM VEST",
					item_variant="GYM VEST-S",
					inward_quantity=400,
					uom="Box",
					stock_entry="FG-1",
					posting_date="2026-07-10",
					warehouse="FG",
				),
				row(
					lot="LOT-1",
					item="GYM VEST",
					item_variant="GYM VEST-M",
					inward_quantity=500,
					uom="Box",
					stock_entry="FG-2",
					posting_date="2026-07-10",
					warehouse="FG",
				),
			],
			stock={},
			warehouses=[],
			variant_attributes={"GYM VEST-S": "S", "GYM VEST-M": "M"},
			column_order=["S", "M"],
		)

		details = {
			detail["primary_attribute_value"]: detail
			for detail in result["ppos"][0]["details"]
		}
		self.assertEqual(details["S"]["wip_quantity"], 100)
		self.assertEqual(details["M"]["wip_quantity"], -100)
		self.assertEqual(result["summary"]["ppo_quantity"], 900)
		self.assertEqual(result["summary"]["inward_quantity"], 900)
		self.assertEqual(result["summary"]["wip_quantity"], 0)
		self.assertEqual(result["summary"]["over_inward_quantity"], 0)

	def test_uses_work_order_movements_for_lot_stage(self):
		result = build_production_snapshot(
			filters={"item": "GYM VEST"},
			ppo_rows=[
				row(
					name="PPO-1",
					item="GYM VEST",
					delivery_date="2026-07-01",
					item_variant="GYM VEST-S",
					quantity=100,
				)
			],
			lot_rows=[
				row(
					lot="LOT-1",
					production_order="PPO-1",
					lot_item="GYM VEST",
					status="Open",
					has_transferred=0,
					is_transferred=0,
					transferred_lot=None,
					packing_combo=10,
					uom="Box",
					packing_uom="Pieces",
					item="GYM VEST",
					item_variant="GYM VEST-S",
					planned_quantity=100,
				)
			],
			stage_rows=[
				row(
					lot="LOT-1",
					production_stage="Packing",
					cutting_work_orders=["WO-CUT-1"],
					stitching_work_orders=["WO-STITCH-1"],
					stitching_has_delivery_challan=True,
					stitching_has_goods_received_note=True,
				)
			],
			inward_rows=[
				row(
					lot="LOT-1",
					item="GYM VEST",
					item_variant="GYM VEST-S",
					inward_quantity=40,
					uom="Box",
					stock_entry="FG-1",
					posting_date="2026-07-10",
					warehouse="FG",
				)
			],
			stock={},
			warehouses=[],
			variant_attributes={"GYM VEST-S": "S"},
			column_order=["S"],
		)

		lot = result["lots"][0]
		ppo = result["ppos"][0]
		self.assertEqual(lot["production_stage"], "Packing")
		self.assertTrue(
			lot["stage_details"]["stitching_has_delivery_challan"]
		)
		self.assertTrue(
			lot["stage_details"]["stitching_has_goods_received_note"]
		)
		self.assertEqual(ppo["inward_quantity"], 40)
		self.assertEqual(ppo["wip_quantity"], 60)
		self.assertEqual(ppo["production_stage"], "Packing")

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
