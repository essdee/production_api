from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import call, patch

from production_api.production_api.doctype.goods_received_note.goods_received_note import (
    GoodsReceivedNote,
)


EXEMPT_SUPPLIER_DOCTYPE = "GRN Quantity Validation Exempt Supplier"


class TestGRNSewingPlanQuantity(TestCase):
    def setUp(self):
        self.grn = self.make_grn()

    def make_grn(self, supplier="SUPPLIER-LOCATION-1", quantity=6):
        return SimpleNamespace(
            name="GRN-TEST-SEWING-QTY",
            against="Work Order",
            against_id="WO-TEST-SEWING-QTY",
            supplier=supplier,
            is_return=0,
            avoid_sewing_plan_qty=0,
            items=[
                SimpleNamespace(
                    item_variant="ITEM-VARIANT-S",
                    quantity=quantity,
                )
            ],
        )

    @patch("frappe.db.sql")
    @patch("frappe.db.get_single_value")
    @patch("frappe.db.exists")
    def test_exempt_supplier_skips_quantity_comparison(
        self, mock_exists, mock_get_single_value, mock_sql
    ):
        mock_exists.side_effect = [True, True]

        GoodsReceivedNote.validate_sewing_plan_quantity(self.grn)

        self.assertEqual(
            mock_exists.call_args_list,
            [
                call("Sewing Plan", {"work_order": "WO-TEST-SEWING-QTY"}),
                call(
                    EXEMPT_SUPPLIER_DOCTYPE,
                    {
                        "parent": "MRP Settings",
                        "parenttype": "MRP Settings",
                        "parentfield": "grn_quantity_validation_exempt_suppliers",
                        "supplier": "SUPPLIER-LOCATION-1",
                    },
                ),
            ],
        )
        mock_get_single_value.assert_not_called()
        mock_sql.assert_not_called()

    @patch("frappe.db.sql")
    @patch("frappe.db.get_single_value", return_value="Checking Output")
    @patch("frappe.db.exists", side_effect=[True, False])
    def test_non_exempt_supplier_keeps_quantity_comparison(
        self, mock_exists, _mock_get_single_value, mock_sql
    ):
        def sql_result(query, *_args, **_kwargs):
            if "tabSewing Plan Detail" in query:
                return [SimpleNamespace(variant="ITEM-VARIANT-S", qty=5)]
            if "tabGoods Received Note Item" in query:
                return []
            return []

        mock_sql.side_effect = sql_result

        with patch("frappe.throw") as mock_throw:
            GoodsReceivedNote.validate_sewing_plan_quantity(self.grn)

        self.assertEqual(mock_exists.call_count, 2)
        quantity_queries = [
            call.args[0]
            for call in mock_sql.call_args_list
            if "tabSewing Plan Detail" in call.args[0]
            or "tabGoods Received Note Item" in call.args[0]
        ]
        self.assertEqual(len(quantity_queries), 2)
        mock_throw.assert_called_once()
        self.assertIn("ITEM-VARIANT-S", mock_throw.call_args.args[0])
