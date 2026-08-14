from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from production_api.production_api.doctype.goods_received_note.goods_received_note import (
    GoodsReceivedNote,
)


class TestClosedWorkOrderSewingGRN(TestCase):
    def make_grn(self, special=False, trusted=False):
        grn = GoodsReceivedNote(
            {
                "doctype": "Goods Received Note",
                "against": "Work Order",
                "against_id": "WO-TEST-CLOSED",
                "from_closed_wo_sewing_details": int(special),
                "items": [],
                "grn_deliverables": [],
            }
        )
        if trusted:
            grn.flags.allow_closed_wo_sewing_details_grn = True
        return grn

    @patch("frappe.get_value", return_value="Close")
    def test_direct_closed_work_order_grn_remains_blocked(self, _get_value):
        grn = self.make_grn()
        with self.assertRaises(frappe.ValidationError):
            grn.validate()

    @patch("frappe.get_value", return_value="Close")
    def test_client_cannot_forge_sewing_details_marker(self, _get_value):
        grn = self.make_grn(special=True)
        with self.assertRaises(frappe.ValidationError):
            grn.validate()

    @patch("frappe.get_value", return_value="Close")
    def test_trusted_sewing_details_route_allows_closed_work_order(self, _get_value):
        grn = self.make_grn(special=True, trusted=True)
        with (
            patch.object(grn, "validate_data") as validate_data,
            patch.object(grn, "validate_dynamic_packing") as validate_packing,
        ):
            grn.validate()

        validate_data.assert_called_once_with()
        validate_packing.assert_called_once_with()

    def test_before_save_never_stores_deliverables_for_special_route(self):
        grn = self.make_grn(special=True, trusted=True)
        grn.grn_deliverables = [{"item_variant": "RAW-MATERIAL", "quantity": 5}]
        grn.grn_excess_usage_items = [{"item_variant": "EXCESS", "quantity": 1}]
        grn.is_return = 0

        with patch.object(grn, "dump_items"):
            grn.before_save()

        self.assertEqual(grn.grn_deliverables, [])
        self.assertEqual(grn.grn_excess_usage_items, [])

    def test_submit_receives_finished_items_without_reducing_material_again(self):
        grn = self.make_grn(special=True, trusted=True)
        grn.update(
            {
                "name": "GRN-TEST-CLOSED-WO",
                "is_return": 0,
                "is_rework": 0,
                "supplier_address": "UNIT-ADDRESS",
                "delivery_address": "MAIN-ADDRESS",
                "is_internal_unit": 0,
                "lot": "LOT-TEST",
                "additional_grn": 0,
                "allow_non_bundle": 0,
                "cut_panel_movement": None,
                "items": [],
                "process_name": "Stitching",
            }
        )

        with (
            patch(
                "production_api.production_api.doctype.delivery_challan.delivery_challan.get_variant_stock_details",
                return_value={},
            ),
            patch("frappe.db.get_single_value", return_value="LOT-TEST"),
            patch.object(grn, "update_work_order_receivables") as update_receivables,
            patch.object(grn, "update_wo_stock_ledger") as receive_finished_stock,
            patch.object(grn, "reduce_uncalculated_stock") as reduce_material,
            patch.object(grn, "reduce_rework_stock") as reduce_rework,
            patch.object(grn, "make_repost_action"),
            patch.object(grn, "piece_calculation") as piece_calculation,
            patch.object(grn, "generate_rework_docs"),
            patch.object(grn, "update_finishing_doc"),
        ):
            grn.on_submit()

        update_receivables.assert_called_once_with()
        receive_finished_stock.assert_called_once_with({})
        reduce_material.assert_not_called()
        reduce_rework.assert_not_called()
        piece_calculation.assert_called_once_with()

    def test_cancel_reverses_finished_receipt_without_restoring_material(self):
        grn = self.make_grn(special=True)
        grn.update(
            {
                "name": "GRN-TEST-CLOSED-WO",
                "docstatus": 2,
                "is_return": 0,
                "is_rework": 0,
                "supplier_address": "UNIT-ADDRESS",
                "delivery_address": "MAIN-ADDRESS",
                "is_internal_unit": 0,
                "lot": "LOT-TEST",
                "additional_grn": 0,
                "allow_non_bundle": 0,
                "cut_panel_movement": None,
                "process_name": "Stitching",
                "items": [
                    {
                        "item_variant": "ITEM-VARIANT-S",
                        "ref_docname": "WO-REC-1",
                        "quantity": 2,
                    }
                ],
            }
        )
        receivable = frappe._dict(name="WO-REC-1", pending_quantity=5)
        work_order = MagicMock(receivables=[receivable])

        with (
            patch("frappe.get_doc", return_value=work_order),
            patch(
                "production_api.production_api.doctype.delivery_challan.delivery_challan.get_variant_stock_details",
                return_value={},
            ),
            patch("frappe.db.get_single_value", return_value="LOT-TEST"),
            patch("frappe.db.sql"),
            patch.object(grn, "reupdate_stock_ledger") as reverse_finished_stock,
            patch.object(grn, "reupdate_wo_deliverables") as restore_material,
            patch.object(grn, "reupdate_rework_stock") as restore_rework,
            patch.object(grn, "make_repost_action"),
            patch.object(grn, "piece_calculation") as piece_calculation,
            patch.object(grn, "generate_rework_docs"),
            patch.object(grn, "update_finishing_doc"),
        ):
            grn.on_cancel()

        self.assertEqual(receivable.pending_quantity, 7)
        work_order.save.assert_called_once_with(ignore_permissions=True)
        reverse_finished_stock.assert_called_once_with({})
        restore_material.assert_not_called()
        restore_rework.assert_not_called()
        piece_calculation.assert_called_once_with()
