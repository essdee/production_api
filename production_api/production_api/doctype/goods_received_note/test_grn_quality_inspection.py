from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from production_api.production_api.doctype.goods_received_note.goods_received_note import (
    GoodsReceivedNote,
)


class TestGRNQualityInspection(TestCase):
    def setUp(self):
        self.grn = SimpleNamespace(
            against="Work Order",
            against_id="WO-TEST-EQI",
            is_return=0,
            lot="LOT-TEST-EQI",
            items=[
                SimpleNamespace(
                    item_variant="GARMENT-RED-M",
                    quantity=10,
                    set_combination={"major_colour": "Red"},
                )
            ],
        )

    @staticmethod
    def get_value(doctype, _name, _fields):
        if doctype == "Work Order":
            return "IPD-TEST-EQI"
        return 0, "Colour", "Size", None, None

    @patch(
        "production_api.production_api.doctype.goods_received_note.goods_received_note.get_variant_attr_details",
        return_value={"Colour": "Red", "Size": "M"},
    )
    @patch("frappe.get_value")
    @patch("frappe.db.sql")
    @patch("frappe.db.exists", return_value=True)
    def test_submitted_passed_inspection_allows_grn(
        self, _mock_exists, mock_sql, mock_get_value, _mock_attributes
    ):
        mock_get_value.side_effect = self.get_value
        mock_sql.return_value = [SimpleNamespace(colour="Red", size="M")]

        with patch("frappe.throw") as mock_throw:
            GoodsReceivedNote.validate_eqi_entered(self.grn)

        mock_throw.assert_not_called()
        self.assertIn("AND e.result = 'Pass'", mock_sql.call_args.args[0])

    @patch(
        "production_api.production_api.doctype.goods_received_note.goods_received_note.get_variant_attr_details",
        return_value={"Colour": "Red", "Size": "M"},
    )
    @patch("frappe.get_value")
    @patch("frappe.db.sql", return_value=[])
    @patch("frappe.db.exists", return_value=True)
    def test_submitted_hold_or_fail_inspection_blocks_grn(
        self, _mock_exists, mock_sql, mock_get_value, _mock_attributes
    ):
        mock_get_value.side_effect = self.get_value

        with patch("frappe.throw") as mock_throw:
            GoodsReceivedNote.validate_eqi_entered(self.grn)

        self.assertIn("AND e.result = 'Pass'", mock_sql.call_args.args[0])
        mock_throw.assert_called_once()
        self.assertIn("result Pass", mock_throw.call_args.args[0])
        self.assertEqual(
            mock_throw.call_args.kwargs["title"],
            "Passed Quality Inspection Missing",
        )
