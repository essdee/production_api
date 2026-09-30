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


class TestPackingReceivableUomConversion(TestCase):
    @staticmethod
    def _uom_details(_item_variant, uom, quantity):
        factor = {"Pieces": 1, "Box": 5}[uom]
        return {
            "stock_uom": "Pieces",
            "conversion_factor": factor,
            "stock_qty": quantity * factor,
        }

    def test_converts_legacy_box_receivable_to_dynamic_pieces(self):
        with patch.object(
            goods_received_note,
            "get_uom_details",
            side_effect=self._uom_details,
        ):
            available = goods_received_note.convert_quantity_between_uoms(
                "PACK-8-10", 514, "Box", "Pieces"
            )
            received = goods_received_note.convert_quantity_between_uoms(
                "PACK-8-10", 1812, "Pieces", "Box"
            )

        self.assertEqual(available, 2570)
        self.assertEqual(received, 362.4)

    def test_dynamic_packing_accepts_pieces_against_legacy_box_receivable(self):
        receivable = _dict(
            name="WO-RECEIVABLE-1",
            item_variant="PACK-8-10",
            pending_quantity=514,
            uom="Box",
        )
        work_order = _dict(receivables=[receivable])

        def get_value(doctype, name, fieldname):
            if doctype == "Lot":
                return ("PRODUCT", "IPD-TEST", "Box", "Pieces", "Pack")
            if doctype == "Item Production Detail":
                return "Size"
            raise AssertionError((doctype, name, fieldname))

        def get_single_value(doctype, fieldname):
            return {
                ("IPD Settings", "default_loose_piece_stage"): "Loose Piece",
                ("Stock Settings", "default_received_type"): "Accepted",
            }[(doctype, fieldname)]

        with (
            patch.object(goods_received_note.frappe, "get_value", side_effect=get_value),
            patch.object(
                goods_received_note.frappe.db,
                "get_single_value",
                side_effect=get_single_value,
            ),
            patch.object(
                goods_received_note.frappe,
                "get_cached_doc",
                return_value=work_order,
            ),
            patch.object(goods_received_note, "is_dynamic_packing_grn", return_value=True),
            patch.object(goods_received_note, "build_variant_attributes", return_value={}),
            patch.object(
                goods_received_note,
                "get_or_create_variant",
                side_effect=["LOOSE-8-10", "PACK-8-10"],
            ),
            patch.object(
                goods_received_note,
                "get_uom_details",
                side_effect=self._uom_details,
            ),
        ):
            items, total_qty = goods_received_note.save_grn_packing_item_details(
                {"8-10": 1812},
                "LOT-TEST",
                _dict(against_id="WO-TEST"),
            )

        self.assertEqual(total_qty, 1812)
        self.assertEqual(items[0]["quantity"], 1812)
        self.assertEqual(items[0]["uom"], "Pieces")
        self.assertEqual(items[0]["ref_docname"], "WO-RECEIVABLE-1")

    def test_submit_reduces_legacy_receivable_in_its_own_uom(self):
        receivable = MagicMock()
        receivable.name = "WO-RECEIVABLE-1"
        receivable.item_variant = "PACK-8-10"
        receivable.pending_quantity = 514
        receivable.uom = "Box"
        receivable.set.side_effect = lambda field, value: setattr(
            receivable, field, value
        )

        work_order = MagicMock()
        work_order.receivables = [receivable]
        work_order.work_order_excess_usage_items = []

        grn = SimpleNamespace(
            docstatus=1,
            against="Work Order",
            against_id="WO-TEST",
            items=[_dict(
                item_variant="PACK-8-10",
                quantity=1812,
                uom="Pieces",
                ref_docname="WO-RECEIVABLE-1",
            )],
            grn_excess_usage_items=[],
        )

        with (
            patch.object(goods_received_note.frappe, "get_doc", return_value=work_order),
            patch.object(
                goods_received_note,
                "get_uom_details",
                side_effect=self._uom_details,
            ),
        ):
            goods_received_note.GoodsReceivedNote.update_work_order_receivables(grn)

        self.assertAlmostEqual(receivable.pending_quantity, 151.6)
        work_order.save.assert_called_once_with(ignore_permissions=True)
