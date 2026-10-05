import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import frappe
from frappe.utils import get_datetime

from production_api.production_api.page.audit_pending_finishing_plans import (
    audit_pending_finishing_plans as dashboard,
)


class TestAuditPendingFinishingPlans(TestCase):
    def test_status_since_uses_latest_transition_into_the_current_status(self):
        plans = [
            frappe._dict(name="FP-1", fp_status="Fully Dispatched"),
            frappe._dict(name="FP-2", fp_status="Dispatched"),
        ]
        versions = [
            frappe._dict(
                docname="FP-1",
                creation="2026-09-12 09:00:00",
                data=json.dumps(
                    {"changed": [["fp_status", "Dispatched", "Fully Dispatched"]]}
                ),
            ),
            frappe._dict(
                docname="FP-1",
                creation="2026-09-01 09:00:00",
                data=json.dumps(
                    {"changed": [["fp_status", "Ready to Pack", "Dispatched"]]}
                ),
            ),
            frappe._dict(
                docname="FP-2",
                creation="2026-09-08 11:30:00",
                data=json.dumps(
                    {"changed": [["comments", "", "checked"]]}
                ),
            ),
            frappe._dict(
                docname="FP-2",
                creation="2026-09-06 10:00:00",
                data=json.dumps(
                    {"changed": [["fp_status", "Ready to Pack", "Dispatched"]]}
                ),
            ),
        ]

        result = dashboard._find_status_since(plans, versions)

        self.assertEqual(result["FP-1"], get_datetime("2026-09-12 09:00:00"))
        self.assertEqual(result["FP-2"], get_datetime("2026-09-06 10:00:00"))

    def test_status_since_ignores_malformed_versions_and_missing_transitions(self):
        plans = [frappe._dict(name="FP-1", fp_status="Dispatched")]
        versions = [
            frappe._dict(docname="FP-1", creation="2026-09-01", data="not-json"),
            frappe._dict(
                docname="FP-1",
                creation="2026-09-02",
                data=json.dumps({"changed": [["comments", "", "x"]]}),
            ),
        ]

        self.assertEqual(dashboard._find_status_since(plans, versions), {})

    def test_overdue_rows_exclude_exactly_seven_days_and_sort_oldest_first(self):
        as_of = get_datetime("2026-10-05 12:00:00")
        plans = [
            frappe._dict(name="FP-8", lot="LOT-8", item="Item 8", fp_status="Dispatched"),
            frappe._dict(name="FP-19", lot="LOT-19", item="Item 19", fp_status="Fully Dispatched"),
            frappe._dict(name="FP-7", lot="LOT-7", item="Item 7", fp_status="Dispatched"),
        ]
        status_since = {
            "FP-8": get_datetime("2026-09-27 12:00:00"),
            "FP-19": get_datetime("2026-09-16 12:00:00"),
            "FP-7": get_datetime("2026-09-28 12:00:00"),
        }
        metrics = {
            "FP-8": {"total_cut": 100, "sewing_received": 98, "packed": 95, "dispatched": 80},
            "FP-19": {"total_cut": 200, "sewing_received": 195, "packed": 190, "dispatched": 188},
            "FP-7": {"total_cut": 50, "sewing_received": 49, "packed": 48, "dispatched": 40},
        }
        histories = {
            "FP-19": [
                frappe._dict(
                    source_doctype="Finishing Plan Dispatch",
                    source_name="FPD-2",
                    stock_entry="STE-2",
                    posting_date="2026-09-16",
                    posting_time="12:00:00",
                    dispatch_boxes=2,
                    dispatch_pieces=100,
                    cancelled=1,
                ),
                frappe._dict(
                    source_doctype="Finishing Plan Dispatch",
                    source_name="FPD-1",
                    stock_entry="STE-1",
                    posting_date="2026-09-15",
                    posting_time="12:00:00",
                    dispatch_boxes=4,
                    dispatch_pieces=188,
                    cancelled=0,
                    destination="WH-Main",
                    operator="Jane Doe",
                ),
            ]
        }

        rows = dashboard._build_overdue_rows(
            plans, status_since, metrics, histories, as_of
        )

        self.assertEqual([row["name"] for row in rows], ["FP-19", "FP-8"])
        self.assertEqual(rows[0]["age_days"], 19)
        self.assertEqual(len(rows[0]["dispatch_history"]), 1)
        self.assertEqual(rows[0]["latest_dispatch"]["document"], "FPD-1")
        self.assertEqual(rows[1]["age_days"], 8)

    def test_summary_counts_each_status_and_oldest_age(self):
        rows = [
            {"fp_status": "Fully Dispatched", "age_days": 19},
            {"fp_status": "Dispatched", "age_days": 15},
            {"fp_status": "Dispatched", "age_days": 8},
        ]

        self.assertEqual(
            dashboard._summarize(rows),
            {"overdue": 3, "dispatched": 2, "fully_dispatched": 1, "oldest_days": 19},
        )

    def test_plan_metrics_support_dynamic_and_legacy_packing(self):
        finishing_plan = SimpleNamespace(
            pieces_per_box=10,
            finishing_plan_details=[
                SimpleNamespace(cutting_qty=60, delivered_quantity=55),
                SimpleNamespace(cutting_qty=40, delivered_quantity=37),
            ],
            finishing_plan_grn_details=[
                SimpleNamespace(quantity=4, dispatched=3),
                SimpleNamespace(quantity=2, dispatched=1),
            ],
        )

        legacy = dashboard._build_plan_metrics(
            finishing_plan,
            frappe._dict(dynamic_ratio_packing=False),
            set_item_parts_count=2,
        )
        dynamic = dashboard._build_plan_metrics(
            finishing_plan,
            frappe._dict(
                dynamic_ratio_packing=True,
                total_packed=97,
                total_dispatched=91,
            ),
            set_item_parts_count=2,
        )

        self.assertEqual(
            legacy,
            {"total_cut": 100.0, "sewing_received": 92.0, "packed": 120.0, "dispatched": 80.0},
        )
        self.assertEqual(
            dynamic,
            {"total_cut": 100.0, "sewing_received": 92.0, "packed": 97.0, "dispatched": 91.0},
        )

    def test_dynamic_dispatch_rows_keep_batch_boxes_and_size_pieces(self):
        rows = dashboard._build_dynamic_dispatch_rows(
            [
                {
                    "finishing_plan": "FP-1",
                    "colour": "Black",
                    "pieces_per_box": 50,
                    "box_quantity": 2,
                    "size_pieces": {"L": 100, "XL": 95},
                },
                {
                    "finishing_plan": "FP-OTHER",
                    "colour": "Navy",
                    "pieces_per_box": 40,
                    "box_quantity": 1,
                    "size_pieces": {"M": 40},
                },
            ],
            "FP-1",
        )

        self.assertEqual(
            rows,
            [
                {"size": "L", "detail": "Black", "pieces_per_box": 50.0, "boxes": 2.0, "pieces": 100.0},
                {"size": "XL", "detail": "Black", "pieces_per_box": 50.0, "boxes": 2.0, "pieces": 95.0},
            ],
        )

    def test_dynamic_dispatch_rows_allow_unscoped_batches_for_direct_dispatch(self):
        rows = dashboard._build_dynamic_dispatch_rows(
            [
                {
                    "colour": "Black",
                    "pieces_per_box": 50,
                    "box_quantity": 2,
                    "size_pieces": {"L": 100},
                },
                {
                    "finishing_plan": "FP-OTHER",
                    "colour": "Navy",
                    "pieces_per_box": 40,
                    "box_quantity": 1,
                    "size_pieces": {"M": 40},
                },
            ],
            "FP-1",
            include_unscoped=True,
        )

        self.assertEqual(
            rows,
            [
                {
                    "size": "L",
                    "detail": "Black",
                    "pieces_per_box": 50.0,
                    "boxes": 2.0,
                    "pieces": 100.0,
                }
            ],
        )

    @patch.object(dashboard.frappe, "get_roles", return_value=["Accounts User"])
    @patch.object(dashboard.frappe.db, "exists", return_value=False)
    def test_dispatch_detail_rejects_a_document_outside_the_plan(self, _exists, _roles):
        with self.assertRaises(frappe.PermissionError):
            dashboard.get_dispatch_detail(
                finishing_plan="FP-1",
                source_doctype="Finishing Plan Dispatch",
                source_name="FPD-OTHER",
                stock_entry="STE-OTHER",
            )
