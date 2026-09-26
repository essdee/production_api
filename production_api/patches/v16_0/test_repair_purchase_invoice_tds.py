from unittest import TestCase
from unittest.mock import Mock, patch

import frappe
from production_api.patches.v16_0 import repair_purchase_invoice_tds as repair


class TestMRPTDSRepair(TestCase):
    def invoice(self):
        doc = Mock(docstatus=1, erp_inv_name="PI-1", vendor_bill_tracking=None, doctype="Purchase Invoice")
        doc.name = "MRP-1"
        return doc

    def row(self):
        return {"erp_invoice": "PI-1", "mrp_invoice": "MRP-1", "modified": "version", "vendor_bill_tracking": None, "comparison": {}}

    def test_dry_run_makes_no_remote_request_or_writes(self):
        inv = self.invoice()
        with (
            patch.object(frappe, "db", new=Mock()) as db,
            patch.object(frappe, "get_doc", return_value=inv),
            patch.object(repair, "post_erp_request") as request,
        ):
            db.exists.return_value = False
            self.assertEqual(repair.repair_one(self.row(), False)["status"], "local_preflight_passed")
            request.assert_not_called()
            inv.save.assert_not_called()
            db.commit.assert_not_called()

    def test_success_updates_mrp_without_resubmitting(self):
        inv = self.invoice()
        response = {"old_name": "PI-1", "name": "PI-1-1", "mrp_invoice": "MRP-1", "docstatus": 1,
                    "vendor_bill_tracking": None, "tds": 100, "withholding_tracked": True, "amount": 900, "due_date": "2026-09-30"}
        with (
            patch.object(frappe, "db", new=Mock()) as db,
            patch.object(frappe, "get_doc", return_value=inv),
            patch.object(repair, "post_erp_request") as request,
        ):
            db.exists.return_value = False
            request.return_value.json.return_value = {"message": response}
            self.assertEqual(repair.repair_one(self.row(), True, repair.repair_one(self.row(), False))["status"], "repaired")
            inv.update.assert_called_once_with({"erp_inv_name": "PI-1-1", "erp_inv_docstatus": 1,
                                               "final_amount": 900, "due_date": "2026-09-30"})
            inv.save.assert_called_once_with()
            inv.submit.assert_not_called()
            inv.cancel.assert_not_called()

    def test_changed_link_blocks_remote_mutation(self):
        inv = self.invoice()
        inv.erp_inv_name = "DIFFERENT"
        with (
            patch.object(frappe, "db", new=Mock()) as db,
            patch.object(frappe, "get_doc", return_value=inv),
            patch.object(frappe, "throw", side_effect=ValueError),
            patch.object(repair, "post_erp_request") as request,
        ):
            db.exists.return_value = False
            with self.assertRaises(ValueError):
                repair.repair_one(self.row(), True)
            request.assert_not_called()

    def test_vendor_links_updated_together(self):
        inv = self.invoice()
        inv.vendor_bill_tracking = "VB-1"
        vendor = Mock(docstatus=1, mrp_purchase_invoice="MRP-1", purchase_invoice="PI-1", form_status="Closed")
        row = {**self.row(), "vendor_bill_tracking": "VB-1"}
        response = {"old_name": "PI-1", "name": "PI-1-1", "mrp_invoice": "MRP-1", "docstatus": 1,
                    "vendor_bill_tracking": "VB-1", "tds": 100, "withholding_tracked": True, "amount": 900, "due_date": "2026-09-30"}
        with (
            patch.object(frappe, "db", new=Mock()) as db,
            patch.object(frappe, "get_doc", side_effect=[inv, vendor, inv, vendor]),
            patch.object(repair, "post_erp_request") as request,
        ):
            db.exists.return_value = False
            request.return_value.json.return_value = {"message": response}
            repair.repair_one(row, True, repair.repair_one(row, False))
            vendor.reopen_vendor_bill.assert_called_once()
            vendor.close_vendor_bill.assert_called_once_with("PI-1-1", "TDS repair of PI-1")
            vendor.save.assert_called_once_with()

    def test_completed_retry_does_not_save_again(self):
        inv = self.invoice()
        inv.erp_inv_name = "PI-1-1"
        response = {"old_name": "PI-1", "name": "PI-1-1", "mrp_invoice": "MRP-1", "docstatus": 1,
                    "vendor_bill_tracking": None, "tds": 0, "withholding_tracked": True,
                    "amount": 1000, "due_date": "2026-09-30"}
        with (
            patch.object(frappe, "db", new=Mock()) as db,
            patch.object(frappe, "get_doc", return_value=inv),
            patch.object(repair, "post_erp_request") as request,
        ):
            db.exists.return_value = True
            request.return_value.json.return_value = {"message": response}
            self.assertEqual(repair.repair_one(self.row(), True)["status"], "already_synced")
            inv.save.assert_not_called()

    def test_stored_dry_run_and_checksum_gate(self):
        import hashlib
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({"schema_version": 2, "invoices": []}))
            report_path = Path(directory) / "review.json"
            with patch.object(frappe, "only_for"), patch.object(frappe, "throw", side_effect=ValueError):
                report = repair.execute(str(manifest), report_file=str(report_path))
                self.assertEqual(report["sha256"], hashlib.sha256(report_path.read_bytes()).hexdigest())
                self.assertEqual(json.loads(report_path.read_text())["manifest"]["schema_version"], 2)
                with self.assertRaises(ValueError):
                    repair.execute(str(manifest), apply=True)
                with self.assertRaises(ValueError):
                    repair.execute(str(manifest), apply=True, report_file=str(report_path), approved_sha256="wrong")
                result = repair.execute(str(manifest), apply=True, report_file=str(report_path), approved_sha256=report["sha256"])
                self.assertTrue(result["apply"])
                manifest.write_text(json.dumps({"schema_version": 2, "invoices": [], "changed": True}))
                with self.assertRaises(ValueError):
                    repair.execute(str(manifest), apply=True, report_file=str(report_path), approved_sha256=report["sha256"])

    def test_newly_linked_erp_invoice_is_skipped_without_local_updates(self):
        inv = self.invoice()
        with (
            patch.object(frappe, "db", new=Mock()) as db,
            patch.object(frappe, "get_doc", return_value=inv),
            patch.object(repair, "post_erp_request") as request,
        ):
            db.exists.return_value = False
            request.return_value.json.return_value = {"message": {
                "status": "skipped", "old_name": "PI-1", "mrp_invoice": "MRP-1", "blockers": ["Payment"]}}
            approved = repair.repair_one(self.row(), False)
            self.assertEqual(repair.repair_one(self.row(), True, approved)["status"], "skipped")
            inv.save.assert_not_called()
            inv.update.assert_not_called()

    def test_http_error_preserves_erp_permission_message(self):
        from requests.exceptions import HTTPError
        inv = self.invoice()
        with (
            patch.object(frappe, "db", new=Mock()) as db,
            patch.object(frappe, "get_doc", return_value=inv),
            patch.object(repair, "post_erp_request") as request,
        ):
            db.exists.return_value = False
            request.return_value.status_code = 403
            request.return_value.raise_for_status.side_effect = HTTPError("Forbidden")
            request.return_value.json.return_value = {"exception": "PermissionError: Cancel not permitted"}
            approved = repair.repair_one(self.row(), False)
            with self.assertRaisesRegex(RuntimeError, "403.*Cancel not permitted"):
                repair.repair_one(self.row(), True, approved)
            inv.save.assert_not_called()
