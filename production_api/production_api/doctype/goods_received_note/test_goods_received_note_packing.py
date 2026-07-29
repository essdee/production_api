# Copyright (c) 2026, Essdee and contributors
# See license.txt

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe
from frappe import _dict

from production_api.production_api.doctype.goods_received_note import goods_received_note


class TestPackingMajorDeliverables(TestCase):
    def test_non_packing_keeps_existing_behaviour(self):
        grn = _dict(includes_packing=0)

        self.assertTrue(
            goods_received_note.should_include_packing_major_deliverables(grn))

    def test_non_group_packing_keeps_existing_behaviour(self):
        grn = _dict(includes_packing=1)
        process = _dict(is_group=0)

        self.assertTrue(
            goods_received_note.should_include_packing_major_deliverables(
                grn, process))

    def test_group_packing_with_finishing_plan_keeps_major_deliverables(self):
        grn = _dict(
            includes_packing=1,
            against_id="WO-WITH-FP",
        )
        process = _dict(is_group=1)

        with patch.object(
            goods_received_note.frappe.db,
            "exists",
            return_value="FP-TEST",
        ) as exists:
            result = goods_received_note.should_include_packing_major_deliverables(
                grn, process)

        self.assertTrue(result)
        exists.assert_called_once_with("Finishing Plan", {
            "work_order": "WO-WITH-FP",
            "docstatus": ["<", 2],
        })

    def test_group_packing_without_finishing_plan_skips_major_deliverables(self):
        grn = _dict(
            includes_packing=1,
            against_id="WO-WITHOUT-FP",
        )
        process = _dict(is_group=1)

        with patch.object(
            goods_received_note.frappe.db,
            "exists",
            return_value=None,
        ):
            result = goods_received_note.should_include_packing_major_deliverables(
                grn, process)

        self.assertFalse(result)

    def test_group_without_finishing_plan_keeps_subprocess_bom_only(self):
        grn_item = _dict(
            item_variant="PRODUCT-Loose Piece-S",
            quantity=10,
            stock_qty=100,
            stock_uom="Pieces",
            uom="Box",
            set_combination={},
        )
        grn = SimpleNamespace(
            includes_packing=1,
            against="Work Order",
            against_id="WO-WITHOUT-FP",
            process_name="Stitching and Packing",
            lot="LOT-TEST",
            posting_date="2026-07-24",
            posting_time="12:00:00",
            items=[grn_item],
        )
        grn.get_packing_piece_values = MagicMock()

        ipd = _dict(
            packing_combo=10,
            item_bom=[
                _dict(
                    item="PACKING BOX",
                    process_name="Packing",
                    based_on_attribute_mapping=0,
                ),
            ],
        )
        lot = _dict()
        process = _dict(
            is_group=1,
            process_details=[_dict(process_name="Stitching"),
                             _dict(process_name="Packing")],
        )
        stock_settings = _dict(default_received_type="Accepted")

        def get_doc(doctype, name):
            return {
                ("Item Production Detail", "IPD-TEST"): ipd,
                ("Lot", "LOT-TEST"): lot,
                ("Process", "Stitching and Packing"): process,
            }[(doctype, name)]

        def get_value(doctype, name, fieldname):
            if doctype == "Lot":
                return ("IPD-TEST", "PRODUCT")
            if doctype == "Work Order":
                return "PRODUCT"
            raise AssertionError((doctype, name, fieldname))

        with (
            patch.object(goods_received_note.frappe, "get_single",
                         return_value=stock_settings),
            patch.object(goods_received_note.frappe, "get_value",
                         side_effect=get_value),
            patch.object(goods_received_note.frappe, "get_doc",
                         side_effect=get_doc),
            patch.object(goods_received_note.frappe, "get_cached_doc",
                         return_value=_dict(default_unit_of_measure="Pieces")),
            patch.object(goods_received_note,
                         "should_include_packing_major_deliverables",
                         return_value=False),
            patch.object(goods_received_note, "get_bom",
                         return_value=(10, "Nos")),
            patch.object(goods_received_note, "get_stock_balance",
                         return_value=(0, 5)),
            patch.object(goods_received_note.frappe.db, "get_single_value",
                         return_value=0),
        ):
            deliverables, excess = (
                goods_received_note.get_packing_process_deliverables(grn))

        self.assertEqual(
            [row["item_variant"] for row in deliverables],
            ["PACKING BOX"],
        )
        self.assertEqual(deliverables[0]["quantity"], 10)
        self.assertEqual(excess, [])
        grn.get_packing_piece_values.assert_not_called()
