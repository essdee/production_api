from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from production_api.production_api.page.sewing_details import sewing_details


class TestStrengthReportPage(TestCase):
    def test_strength_report_is_rendered_on_sewing_details_page(self):
        root_source = Path(
            frappe.get_app_path(
                "production_api", "public", "js", "SewingPlan", "SewingPlan.vue"
            )
        ).read_text()
        component_source = Path(
            frappe.get_app_path(
                "production_api",
                "public",
                "js",
                "SewingPlan",
                "components",
                "StrengthReportTab.vue",
            )
        ).read_text()

        self.assertIn("id: 'strength_report', label: 'Strength Report'", root_source)
        self.assertIn("import StrengthReportTab", root_source)
        self.assertIn("<StrengthReportTab", root_source)
        self.assertIn("grid-template-columns: minmax(0, 2fr) minmax(0, 3fr)", component_source)
        self.assertIn("fieldname: 'strength_report_date'", component_source)
        self.assertIn("fieldname: 'strength_report_from_time'", component_source)
        self.assertIn("fieldname: 'strength_report_to_time'", component_source)
        self.assertIn("employee.first_punch || '-'", component_source)
        self.assertIn("Fetching Workers Strength Report from HR...", component_source)
        self.assertIn("Report fetched successfully.", component_source)
        self.assertIn("Unable to load the Workers Strength Report.", component_source)
        self.assertIn("import * as XLSX from 'xlsx'", component_source)
        self.assertIn("Employee_First_Punch_${reportDate.value}.xlsx", component_source)
        self.assertIn("Workers_Strength_Summary_${reportDate.value}.xlsx", component_source)
        self.assertIn("filteredEmployeePunches", component_source)
        self.assertIn("filteredSummaryRows", component_source)
        self.assertIn("scheduleEmployeeFilters", component_source)
        self.assertIn("scheduleSummaryFilters", component_source)
        self.assertIn("employeeDepartmentFilterInput", component_source)
        self.assertIn("employeeDesignationFilterInput", component_source)
        self.assertIn("<th>Department</th>", component_source)
        self.assertIn("<th>Designation</th>", component_source)
        self.assertIn("['absent_employees', 'leave_employees']", component_source)
        self.assertIn("max-width: 130px", component_source)
        self.assertIn("}, 1000)", component_source)
        self.assertNotIn("Applies 2 seconds after typing", component_source)
        self.assertEqual(component_source.count("frappe.call({"), 1)

    def test_strength_report_fields_are_not_on_sewing_plan_doctype(self):
        meta_source = Path(
            frappe.get_app_path(
                "production_api",
                "production_api",
                "doctype",
                "sewing_plan",
                "sewing_plan.json",
            )
        ).read_text()

        self.assertNotIn('"strength_report_tab"', meta_source)
        self.assertNotIn('"fetch_strength_report"', meta_source)


class FakeGRN:
    def __init__(self):
        self.name = "GRN-TEST-CLOSED-WO"
        self.docstatus = 0
        self.flags = frappe._dict()
        self.values = {}

    def update(self, values):
        self.values.update(values)
        for key, value in values.items():
            setattr(self, key, value)

    def insert(self):
        self.inserted = True

    def submit(self):
        self.submitted = True
        self.docstatus = 1


class TestClosedWorkOrderGRNPage(TestCase):
    @staticmethod
    def make_work_order():
        receivable = frappe._dict(
            name="WO-REC-1",
            item_variant="ITEM-VARIANT-S",
            lot="LOT-TEST",
            qty=100,
            pending_quantity=20,
            secondary_qty=0,
            uom="Pieces",
            secondary_uom=None,
            cost=12.5,
            table_index=1,
            row_index=1,
            comments="",
            set_combination={"major_colour": "Black"},
        )
        return frappe._dict(
            name="WO-TEST-CLOSED",
            docstatus=1,
            open_status="Close",
            supplier="UNIT-TEST",
            supplier_address="UNIT-ADDRESS",
            delivery_location="MAIN-WAREHOUSE",
            delivery_address="MAIN-ADDRESS",
            item="ITEM-TEST",
            lot="LOT-TEST",
            production_detail="IPD-TEST",
            process_name="Stitching",
            is_internal_unit=1,
            is_rework=0,
            includes_packing=0,
            receivables=[receivable],
        )

    @staticmethod
    def make_item_details(ref_docname="WO-REC-1", quantity=5):
        return [
            {
                "items": [
                    {
                        "name": "ATTACKER-ITEM",
                        "attributes": {"Size": "S"},
                        "values": {
                            "S": {
                                "ref_docname": ref_docname,
                                "received": quantity,
                                "types": {"Accepted": quantity},
                                "secondary_qty_json": {},
                                "rate": 9999,
                            }
                        },
                    }
                ]
            }
        ]

    @patch.object(sewing_details, "_make_grn_item_details")
    @patch.object(sewing_details, "_get_closed_sewing_work_order")
    def test_details_return_normal_grn_editor_data(
        self, get_work_order, make_item_details
    ):
        work_order = self.make_work_order()
        work_order.receivables.append(
            frappe._dict(
                name="WO-REC-DONE",
                item_variant="ITEM-VARIANT-M",
                pending_quantity=0,
            )
        )
        get_work_order.return_value = work_order
        editor_data = [{"items": [{"name": "ITEM-TEST"}]}]
        make_item_details.return_value = editor_data

        result = sewing_details.get_closed_work_order_grn_details(
            work_order.name, work_order.supplier
        )

        self.assertTrue(result["has_pending_items"])
        self.assertEqual(result["item_details"], editor_data)
        self.assertEqual(result["supplier_address"], "UNIT-ADDRESS")
        make_item_details.assert_called_once_with(work_order)

    @patch.object(sewing_details.frappe.db, "exists", return_value=True)
    def test_item_selection_accepts_only_quantities_for_work_order_rows(
        self, _exists
    ):
        work_order = self.make_work_order()

        selections = sewing_details._extract_item_selections(
            work_order, self.make_item_details()
        )

        self.assertEqual(selections["WO-REC-1"]["types"], {"Accepted": 5.0})
        self.assertEqual(
            selections["WO-REC-1"]["secondary_qty_json"], {}
        )

    @patch.object(sewing_details, "_make_grn_item_details", return_value=[{"trusted": True}])
    @patch.object(sewing_details.frappe.db, "exists", return_value=True)
    def test_grn_rows_replace_client_item_and_rate_with_server_values(
        self, _exists, make_item_details
    ):
        work_order = self.make_work_order()
        calculated_rows = [
            {
                "ref_docname": "WO-REC-1",
                "quantity": 5,
                "table_index": 3,
                "row_index": 4,
                "item_variant": "ATTACKER-ITEM",
                "rate": 9999,
            }
        ]

        with patch(
            "production_api.production_api.doctype.goods_received_note.goods_received_note.save_grn_item_details",
            return_value=(calculated_rows, 0, 5),
        ) as save_item_details:
            rows = sewing_details._make_grn_rows(
                work_order, self.make_item_details()
            )

        self.assertEqual(rows[0]["item_variant"], "ITEM-VARIANT-S")
        self.assertEqual(rows[0]["rate"], 12.5)
        self.assertEqual(rows[0]["received_types"], {"Accepted": 5.0})
        make_item_details.assert_called_once()
        save_item_details.assert_called_once_with([{"trusted": True}], "Stitching")

    @patch.object(sewing_details, "_make_grn_rows")
    @patch.object(sewing_details.frappe, "new_doc")
    @patch.object(sewing_details, "_get_closed_sewing_work_order")
    @patch.object(sewing_details.frappe, "has_permission", return_value=True)
    def test_create_uses_server_work_order_values_and_trusted_marker(
        self, _has_permission, get_work_order, new_doc, make_grn_rows
    ):
        work_order = self.make_work_order()
        get_work_order.return_value = work_order
        fake_grn = FakeGRN()
        new_doc.return_value = fake_grn
        make_grn_rows.return_value = [
            {
                "ref_docname": "WO-REC-1",
                "item_variant": "ITEM-VARIANT-S",
                "quantity": 5,
                "rate": 12.5,
                "received_types": {"Accepted": 5},
            }
        ]

        item_details = self.make_item_details()
        result = sewing_details.create_closed_work_order_grn(
            work_order.name,
            work_order.supplier,
            {
                "posting_date": "2026-08-14",
                "posting_time": "10:00:00",
                "delivery_date": "2026-08-14",
                "supplier_document_no": "SUP-DOC-1",
                "supplier_document_date": "2026-08-14",
                "vehicle_no": "TN-TEST-1",
            },
            item_details,
        )

        item = fake_grn.values["items"][0]
        self.assertEqual(result, {"name": fake_grn.name, "docstatus": 1})
        self.assertEqual(item["item_variant"], "ITEM-VARIANT-S")
        self.assertEqual(item["rate"], 12.5)
        self.assertEqual(item["received_types"], {"Accepted": 5})
        self.assertEqual(fake_grn.values["from_closed_wo_sewing_details"], 1)
        self.assertEqual(fake_grn.values["grn_deliverables"], [])
        self.assertTrue(fake_grn.flags.allow_closed_wo_sewing_details_grn)
        self.assertTrue(fake_grn.inserted)
        self.assertTrue(fake_grn.submitted)
        get_work_order.assert_called_once_with(
            work_order.name, work_order.supplier, for_update=True
        )
        make_grn_rows.assert_called_once_with(work_order, item_details)

    def test_item_selection_rejects_receivable_from_another_work_order(self):
        work_order = self.make_work_order()

        with self.assertRaises(frappe.ValidationError):
            sewing_details._extract_item_selections(
                work_order, self.make_item_details(ref_docname="OTHER-WO-ROW")
            )

    @patch.object(sewing_details, "_make_grn_item_details")
    @patch.object(sewing_details, "_get_closed_sewing_work_order")
    @patch.object(sewing_details.frappe.db, "get_single_value", return_value="Accepted")
    @patch.object(sewing_details.frappe.db, "exists", return_value=True)
    def test_calculate_updates_normal_item_and_adds_accessory_quantity(
        self, _exists, _default_type, get_work_order, make_item_details
    ):
        work_order = self.make_work_order()
        accessory = frappe._dict(
            name="WO-REC-ACCESSORY",
            item_variant="ACCESSORY-ITEM",
            lot="LOT-TEST",
            pending_quantity=10,
            secondary_uom=None,
            set_combination={},
        )
        work_order.receivables.append(accessory)
        get_work_order.return_value = work_order
        make_item_details.return_value = [{"updated": True}]
        current_selections = {
            "WO-REC-1": {"types": {}, "secondary_qty_json": {}},
            "WO-REC-ACCESSORY": {
                "types": {"Accepted": 1},
                "secondary_qty_json": {},
            },
        }
        calculated = [
            {
                "item_variant": "ITEM-VARIANT-S",
                "set_combination": {"major_colour": "Black"},
                "qty": 5,
                "is_accessory": 0,
            },
            {
                "item_variant": "ACCESSORY-ITEM",
                "set_combination": {},
                "qty": 2,
                "is_accessory": 1,
            },
        ]

        with (
            patch.object(
                sewing_details,
                "_extract_item_selections",
                return_value=current_selections,
            ),
            patch(
                "production_api.production_api.doctype.work_order.work_order.get_deliverable_receivable",
                return_value=calculated,
            ),
        ):
            result = sewing_details.calculate_closed_work_order_receivables(
                work_order.name,
                work_order.supplier,
                [],
                self.make_item_details(),
                "Passed",
            )

        self.assertEqual(result, [{"updated": True}])
        selections = make_item_details.call_args.args[1]
        self.assertEqual(selections["WO-REC-1"]["types"], {"Passed": 5.0})
        self.assertEqual(
            selections["WO-REC-ACCESSORY"]["types"], {"Accepted": 3.0}
        )

    @patch.object(sewing_details.frappe.db, "exists", return_value=False)
    @patch.object(sewing_details.frappe, "get_doc")
    def test_closed_work_order_must_be_linked_to_sewing_details(
        self, get_doc, _exists
    ):
        work_order = self.make_work_order()
        work_order.check_permission = MagicMock()
        get_doc.return_value = work_order

        with self.assertRaises(frappe.ValidationError):
            sewing_details._get_closed_sewing_work_order(
                work_order.name, work_order.supplier
            )

        work_order.check_permission.assert_called_once_with("read")
