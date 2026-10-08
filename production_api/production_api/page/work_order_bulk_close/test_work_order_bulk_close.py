from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import getdate

from production_api.production_api.page.work_order_bulk_close.work_order_bulk_close import (
    close_work_orders,
    get_open_work_orders,
    get_work_order_close_details,
)
from production_api.production_api.page.work_order_bulk_close import (
    work_order_bulk_close as bulk_close_module,
)
from production_api.production_api.doctype.work_order import (
    work_order as work_order_module,
)


class TestWorkOrderBulkClose(TestCase):
    @staticmethod
    def make_mock_work_order():
        work_order = MagicMock()
        work_order.doctype = "Work Order"
        work_order.name = "WO-TEST-CLOSE"
        work_order.open_status = "Open"
        work_order.is_internal_unit = 1
        work_order.no_receivables = True
        work_order.deliverables = []
        return work_order

    @patch("frappe.get_list")
    @patch("frappe.db.exists", return_value=True)
    def test_get_open_work_orders_returns_difference(self, _exists, get_list):
        get_list.return_value = [
            frappe._dict(
                name="WO-TEST-0001",
                wo_date="2026-08-14",
                item="Test Item",
                lot="LOT-TEST-0001",
                process_name="Stitching",
                production_detail="IPD-TEST-0001",
                total_delivered=120,
                total_received=95,
            )
        ]

        work_orders = get_open_work_orders("SUPPLIER-TEST")

        self.assertEqual(work_orders[0].difference, 25)
        get_list.assert_called_once_with(
            "Work Order",
            filters={
                "supplier": "SUPPLIER-TEST",
                "docstatus": 1,
                "open_status": "Open",
            },
            fields=[
                "name",
                "wo_date",
                "item",
                "lot",
                "process_name",
                "production_detail",
                "total_no_of_pieces_delivered as total_delivered",
                "total_no_of_pieces_received as total_received",
            ],
            order_by="modified desc, name desc",
            limit_page_length=0,
        )

    @patch("frappe.get_list", return_value=[])
    @patch("frappe.db.exists", return_value=True)
    def test_get_open_work_orders_applies_optional_filters(
        self, _exists, get_list
    ):
        get_open_work_orders(
            "SUPPLIER-TEST",
            lot=["LOT-TEST-0001", "LOT-TEST-0002"],
            item='["ITEM-TEST-0001", "ITEM-TEST-0002"]',
            wo_from_date="2026-08-01",
            wo_to_date="2026-08-14",
        )

        filters = get_list.call_args.kwargs["filters"]
        self.assertEqual(
            filters["lot"], ["in", ["LOT-TEST-0001", "LOT-TEST-0002"]]
        )
        self.assertEqual(
            filters["item"], ["in", ["ITEM-TEST-0001", "ITEM-TEST-0002"]]
        )
        self.assertEqual(
            filters["wo_date"],
            [
                "between",
                [getdate("2026-08-01"), getdate("2026-08-14")],
            ],
        )

    @patch("frappe.get_list")
    @patch("frappe.db.exists", return_value=True)
    def test_get_open_work_orders_rejects_invalid_date_range(
        self, _exists, get_list
    ):
        with self.assertRaises(frappe.ValidationError):
            get_open_work_orders(
                "SUPPLIER-TEST",
                wo_from_date="2026-08-14",
                wo_to_date="2026-08-01",
            )

        work_order_calls = [
            call
            for call in get_list.call_args_list
            if call.args and call.args[0] == "Work Order"
        ]
        self.assertEqual(work_order_calls, [])

    @patch(
        "production_api.production_api.doctype.work_order.work_order.get_wo_recut_details",
        return_value=[],
    )
    @patch("frappe.has_permission", return_value=False)
    @patch("frappe.get_doc")
    def test_close_details_supports_work_order_without_calculated_items(
        self, get_doc, _has_permission, _get_recut_details
    ):
        work_order = MagicMock()
        work_order.name = "WO-TEST-EMPTY"
        work_order.docstatus = 1
        work_order.open_status = "Open"
        work_order.work_order_calculated_items = []
        get_doc.return_value = work_order

        details = get_work_order_close_details(work_order.name)

        work_order.check_permission.assert_called_once_with("read")
        self.assertEqual(details["summary"]["item_detail"], [])
        self.assertEqual(details["recut_details"], [])
        self.assertEqual(details["debits"], [])

    def test_update_stock_manager_path_closes_work_order(self):
        work_order = self.make_mock_work_order()

        def get_single_value(doctype, _fieldname):
            if doctype == "MRP Settings":
                return "Merchandising Manager"
            if doctype == "Stock Settings":
                return "Received"
            return None

        with (
            patch.object(work_order_module.frappe, "get_doc", return_value=work_order),
            patch.object(
                work_order_module.frappe.db,
                "get_single_value",
                side_effect=get_single_value,
            ),
            patch.object(
                work_order_module.frappe,
                "get_roles",
                return_value=["Merchandising Manager"],
            ),
            patch.object(work_order_module.frappe, "get_all", return_value=[]),
            patch.object(
                work_order_module, "get_variant_stock_details", return_value={}
            ),
            patch.object(work_order_module, "make_sl_entries") as make_sl_entries,
            patch.object(
                work_order_module, "get_module_logger", return_value=MagicMock()
            ),
        ):
            result = work_order_module.update_stock(
                work_order.name,
                close_reason="Others",
                close_other_reason="Test",
                close_remarks="Safe mocked close",
            )

        self.assertEqual(result, {"open_status": "Close"})
        self.assertEqual(work_order.open_status, "Close")
        work_order.save.assert_called_once_with()
        make_sl_entries.assert_called_once_with([])

    def test_update_stock_non_manager_path_submits_close_request(self):
        work_order = self.make_mock_work_order()

        with (
            patch.object(work_order_module.frappe, "get_doc", return_value=work_order),
            patch.object(
                work_order_module.frappe.db,
                "get_single_value",
                return_value="Merchandising Manager",
            ),
            patch.object(work_order_module.frappe, "get_roles", return_value=[]),
            patch.object(work_order_module.frappe, "msgprint"),
        ):
            result = work_order_module.update_stock(
                work_order.name,
                close_reason="Sewing Shortage",
                close_remarks="Safe mocked close request",
            )

        self.assertEqual(result, {"open_status": "Close Request"})
        self.assertEqual(work_order.open_status, "Close Request")
        work_order.save.assert_called_once_with()

    def test_bulk_close_non_manager_closes_company_location_work_order(self):
        work_order = self.make_mock_work_order()
        work_order.docstatus = 1

        def get_single_value(doctype, _fieldname):
            if doctype == "MRP Settings":
                return "Merch Manager"
            if doctype == "Stock Settings":
                return "Received"
            return None

        with (
            patch.object(work_order_module.frappe, "get_doc", return_value=work_order),
            patch.object(
                work_order_module.frappe.db,
                "get_single_value",
                side_effect=get_single_value,
            ),
            patch.object(work_order_module.frappe, "get_roles", return_value=[]),
            patch.object(work_order_module.frappe, "get_all", return_value=[]),
            patch.object(
                work_order_module, "get_variant_stock_details", return_value={}
            ),
            patch.object(work_order_module, "make_sl_entries"),
            patch.object(
                work_order_module, "get_module_logger", return_value=MagicMock()
            ),
        ):
            result = close_work_orders([work_order.name])

        self.assertEqual(
            result,
            {
                "results": [
                    {"work_order": work_order.name, "open_status": "Close"}
                ]
            },
        )
        self.assertEqual(work_order.open_status, "Close")

    def test_bulk_close_non_manager_keeps_external_supplier_approval_flow(self):
        work_order = self.make_mock_work_order()
        work_order.docstatus = 1
        work_order.is_internal_unit = 0

        with (
            patch.object(work_order_module.frappe, "get_doc", return_value=work_order),
            patch.object(
                work_order_module.frappe.db,
                "get_single_value",
                return_value="Merch Manager",
            ),
            patch.object(work_order_module.frappe, "get_roles", return_value=[]),
            patch.object(work_order_module.frappe, "msgprint"),
        ):
            result = close_work_orders([work_order.name])

        self.assertEqual(
            result,
            {
                "results": [
                    {
                        "work_order": work_order.name,
                        "open_status": "Close Request",
                    }
                ]
            },
        )
        self.assertEqual(work_order.open_status, "Close Request")

    def test_approve_close_requests_closes_selected_request_for_manager(self):
        approve_close_requests = getattr(
            bulk_close_module, "approve_close_requests", None
        )
        if not approve_close_requests:
            self.fail("Bulk close-request approval endpoint is missing")

        work_order = self.make_mock_work_order()
        work_order.docstatus = 1
        work_order.open_status = "Close Request"
        work_order.close_reason = "Sewing Shortage"
        work_order.close_other_reason = "NA"
        work_order.close_remarks = "Approved from list"
        work_order.supplier = "SUPPLIER-TEST"
        work_order.lot = "LOT-TEST"
        work_order.deliverables = [
            frappe._dict(
                name="WO-DELIVERABLE-TEST",
                item_variant="ITEM-VARIANT-TEST",
                qty=10,
                pending_quantity=2,
                stock_update=3,
                uom="Nos",
                rate=12,
                docstatus=1,
            )
        ]

        def get_single_value(doctype, _fieldname):
            if doctype == "MRP Settings":
                return "Merch Manager"
            if doctype == "Stock Settings":
                return "Received"
            return None

        with (
            patch.object(work_order_module.frappe, "get_doc", return_value=work_order),
            patch.object(
                work_order_module.frappe.db,
                "get_single_value",
                side_effect=get_single_value,
            ),
            patch.object(
                work_order_module.frappe,
                "get_roles",
                return_value=["Merch Manager"],
            ),
            patch.object(work_order_module.frappe, "get_all", return_value=[]),
            patch.object(
                work_order_module,
                "get_variant_stock_details",
                return_value={"ITEM-VARIANT-TEST": True},
            ),
            patch(
                "production_api.mrp_stock.utils.get_stock_balance",
                return_value=20,
            ),
            patch.object(
                work_order_module, "make_sl_entries"
            ) as make_sl_entries,
            patch.object(
                work_order_module, "get_module_logger", return_value=MagicMock()
            ),
            patch.object(work_order_module, "nowdate", return_value="2026-10-08"),
            patch.object(work_order_module, "nowtime", return_value="12:00:00"),
        ):
            result = approve_close_requests([work_order.name])

        self.assertEqual(
            result,
            {
                "results": [
                    {"work_order": work_order.name, "open_status": "Close"}
                ],
                "failed": [],
            },
        )
        self.assertEqual(work_order.open_status, "Close")
        self.assertEqual(work_order.close_reason, "Sewing Shortage")
        self.assertEqual(work_order.close_remarks, "Approved from list")
        stock_ledger_entries = make_sl_entries.call_args.args[0]
        self.assertEqual(len(stock_ledger_entries), 1)
        self.assertEqual(stock_ledger_entries[0]["item"], "ITEM-VARIANT-TEST")
        self.assertEqual(stock_ledger_entries[0]["warehouse"], "SUPPLIER-TEST")
        self.assertEqual(stock_ledger_entries[0]["lot"], "LOT-TEST")
        self.assertEqual(stock_ledger_entries[0]["qty"], -5)

    def test_approve_close_requests_continues_after_one_work_order_fails(self):
        work_orders = {}
        for name in ("WO-SUCCESS-1", "WO-FAIL", "WO-SUCCESS-2"):
            doc = self.make_mock_work_order()
            doc.name = name
            doc.docstatus = 1
            doc.open_status = "Close Request"
            doc.close_reason = "Sewing Shortage"
            doc.close_other_reason = "NA"
            doc.close_remarks = "Bulk approval"
            work_orders[name] = doc

        attempted = []

        def update_stock(work_order, **_kwargs):
            attempted.append(work_order)
            if work_order == "WO-FAIL":
                raise frappe.ValidationError("GRN GRN-FAIL is not completed")
            return {"open_status": "Close"}

        with (
            patch.object(
                work_order_module.frappe,
                "get_doc",
                side_effect=lambda _doctype, name, **_kwargs: work_orders[name],
            ),
            patch.object(
                work_order_module.frappe.db,
                "get_single_value",
                return_value="Merch Manager",
            ),
            patch.object(
                work_order_module.frappe,
                "get_roles",
                return_value=["Merch Manager"],
            ),
            patch.object(work_order_module.frappe, "get_all", return_value=[]),
            patch.object(work_order_module, "update_stock", side_effect=update_stock),
            patch.object(work_order_module.frappe.db, "savepoint"),
            patch.object(work_order_module.frappe.db, "rollback") as rollback,
        ):
            try:
                result = bulk_close_module.approve_close_requests(
                    list(work_orders)
                )
            except Exception as exc:
                self.fail(f"Bulk approval stopped at the first error: {exc}")

        self.assertEqual(
            attempted,
            ["WO-SUCCESS-1", "WO-FAIL", "WO-SUCCESS-2"],
        )
        self.assertEqual(
            result,
            {
                "results": [
                    {"work_order": "WO-SUCCESS-1", "open_status": "Close"},
                    {"work_order": "WO-SUCCESS-2", "open_status": "Close"},
                ],
                "failed": [
                    {
                        "work_order": "WO-FAIL",
                        "error": "GRN GRN-FAIL is not completed",
                    }
                ],
            },
        )
        rollback.assert_called_once_with(save_point="work_order_close_2")

    def test_approve_close_requests_rejects_non_manager(self):
        work_order = self.make_mock_work_order()
        work_order.docstatus = 1
        work_order.open_status = "Close Request"

        with (
            patch.object(work_order_module.frappe, "get_doc", return_value=work_order),
            patch.object(
                work_order_module.frappe.db,
                "get_single_value",
                return_value="Merch Manager",
            ),
            patch.object(work_order_module.frappe, "get_roles", return_value=[]),
        ):
            with self.assertRaises(frappe.PermissionError):
                bulk_close_module.approve_close_requests([work_order.name])

        self.assertEqual(work_order.open_status, "Close Request")

    def test_approve_close_requests_rejects_work_order_without_pending_request(self):
        work_order = self.make_mock_work_order()
        work_order.docstatus = 1
        work_order.open_status = "Open"

        with (
            patch.object(work_order_module.frappe, "get_doc", return_value=work_order),
            patch.object(
                work_order_module.frappe.db,
                "get_single_value",
                return_value="Merch Manager",
            ),
            patch.object(
                work_order_module.frappe,
                "get_roles",
                return_value=["Merch Manager"],
            ),
            patch.object(work_order_module.frappe, "get_all", return_value=[]),
            patch.object(
                work_order_module, "get_variant_stock_details", return_value={}
            ),
            patch.object(work_order_module, "make_sl_entries"),
            patch.object(
                work_order_module, "get_module_logger", return_value=MagicMock()
            ),
        ):
            result = bulk_close_module.approve_close_requests([work_order.name])

        self.assertEqual(work_order.open_status, "Open")
        self.assertEqual(result["results"], [])
        self.assertEqual(
            result["failed"],
            [
                {
                    "work_order": work_order.name,
                    "error": (
                        f"Work Order {work_order.name} does not have a pending "
                        "Close Request."
                    ),
                }
            ],
        )

    def test_approve_close_requests_rejects_unapproved_debit(self):
        work_order = self.make_mock_work_order()
        work_order.docstatus = 1
        work_order.open_status = "Close Request"

        def get_all(doctype, *args, **kwargs):
            if doctype == "Essdee Debit":
                return [
                    frappe._dict(
                        name="ED-TEST-00001",
                        against_id=work_order.name,
                    )
                ]
            return []

        with (
            patch.object(work_order_module.frappe, "get_doc", return_value=work_order),
            patch.object(
                work_order_module.frappe.db,
                "get_single_value",
                return_value="Merch Manager",
            ),
            patch.object(
                work_order_module.frappe,
                "get_roles",
                return_value=["Merch Manager"],
            ),
            patch.object(
                work_order_module.frappe,
                "get_all",
                side_effect=get_all,
            ),
            patch.object(
                work_order_module, "get_variant_stock_details", return_value={}
            ),
            patch.object(work_order_module, "make_sl_entries"),
            patch.object(
                work_order_module, "get_module_logger", return_value=MagicMock()
            ),
        ):
            result = bulk_close_module.approve_close_requests([work_order.name])

        self.assertEqual(work_order.open_status, "Close Request")
        self.assertEqual(result["results"], [])
        self.assertEqual(
            result["failed"],
            [
                {
                    "work_order": work_order.name,
                    "error": "Approve Essdee Debit ED-TEST-00001 before closing.",
                }
            ],
        )

    def test_update_stock_stores_na_for_empty_close_details(self):
        work_order = self.make_mock_work_order()

        with (
            patch.object(work_order_module.frappe, "get_doc", return_value=work_order),
            patch.object(
                work_order_module.frappe.db,
                "get_single_value",
                return_value="Merchandising Manager",
            ),
            patch.object(work_order_module.frappe, "get_roles", return_value=[]),
            patch.object(work_order_module.frappe, "msgprint"),
        ):
            work_order_module.update_stock(work_order.name)

        self.assertEqual(work_order.close_reason, "NA")
        self.assertEqual(work_order.close_other_reason, "NA")
        self.assertEqual(work_order.close_remarks, "NA")

    @patch.object(work_order_module, "update_stock")
    @patch("frappe.get_doc")
    def test_bulk_close_validates_all_then_closes_with_shared_details(
        self, get_doc, update_stock
    ):
        first = MagicMock(docstatus=1, open_status="Open")
        second = MagicMock(docstatus=1, open_status="Open")
        get_doc.side_effect = [first, second]
        update_stock.side_effect = [
            {"open_status": "Close"},
            {"open_status": "Close"},
        ]

        result = close_work_orders(
            ["WO-TEST-0001", "WO-TEST-0002"],
            close_reason="Sewing Shortage",
            close_remarks="Shared remark",
        )

        first.check_permission.assert_called_once_with("write")
        second.check_permission.assert_called_once_with("write")
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(update_stock.call_count, 2)
        update_stock.assert_any_call(
            "WO-TEST-0001",
            close_reason="Sewing Shortage",
            close_other_reason=None,
            close_remarks="Shared remark",
        )

    @patch.object(work_order_module, "update_stock")
    @patch("frappe.get_doc")
    def test_bulk_close_does_not_update_any_work_order_if_validation_fails(
        self, get_doc, update_stock
    ):
        get_doc.side_effect = [
            MagicMock(docstatus=1, open_status="Open"),
            MagicMock(docstatus=1, open_status="Close"),
        ]

        with self.assertRaises(frappe.ValidationError):
            close_work_orders(["WO-TEST-0001", "WO-TEST-0002"])

        update_stock.assert_not_called()
