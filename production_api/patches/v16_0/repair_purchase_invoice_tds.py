"""Run explicitly with a reviewed Essdee TDS manifest; not a migration patch.

Dry-run is the default. Each ERP amendment commits remotely before the local
MRP/Vendor Bill Tracking update. Retry the SAME manifest after a failure: the
ERP endpoint returns the existing amendment instead of creating a duplicate.
"""

import json
import hashlib
import os
import time
from pathlib import Path

import frappe
from requests.exceptions import HTTPError
from frappe.utils import cint, getdate
from production_api.production_api.doctype.mrp_settings.mrp_settings import post_erp_request


ENDPOINT = "/api/method/essdee.essdee.utils.mrp.repair_purchase_invoice_tds.repair"


def execute(manifest_file, apply=False, report_file=None, approved_sha256=None):
    frappe.only_for("System Manager")
    manifest_bytes = Path(manifest_file).read_bytes()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes)
    if manifest.get("simulation_only") or any(row.get("error") for row in manifest.get("invoices", [])):
        frappe.throw("Generate a fresh ERP manifest after resolving withholding history errors; simulations cannot be applied")
    if manifest.get("schema_version") != 2:
        frappe.throw("Generate a new ERP manifest with stored before/after comparisons")
    approved_rows = {}
    if cint(apply):
        if not report_file or not approved_sha256:
            frappe.throw("Run and review the dry run first; its report_file and approved_sha256 are required")
        raw_report = Path(report_file).read_bytes()
        if hashlib.sha256(raw_report).hexdigest() != approved_sha256:
            frappe.throw("Approved dry-run report checksum does not match")
        approved = json.loads(raw_report)
        if approved.get("manifest_sha256") != manifest_hash or approved.get("apply") is not False:
            frappe.throw("Dry-run report does not match this exact manifest")
        if any(row.get("status") == "failed" for row in approved["results"]):
            frappe.throw("Dry run has failures; resolve them and generate a new report")
        approved_rows = {row["old_name"]: row for row in approved["results"]}
    rows = manifest["invoices"]
    if any(getdate(row["creation"]) < getdate("2026-09-13") for row in rows):
        frappe.throw("Manifest includes invoices created before the v16 migration on 2026-09-13")
    mrp_names = [r["mrp_invoice"] for r in rows if r.get("mrp_invoice")]
    if len({r["erp_invoice"] for r in rows}) != len(rows) or len(set(mrp_names)) != len(mrp_names):
        frappe.throw("Manifest contains duplicate ERP or MRP invoices")
    results = []
    for row in sorted(rows, key=lambda r: (r["posting_date"], r["creation"], r["erp_invoice"])):
        if not row.get("repair_candidate") or row.get("blockers"):
            results.append({"old_name": row["erp_invoice"], "status": "skipped", "blockers": row.get("blockers")})
            continue
        try:
            if not row.get("comparison"):
                frappe.throw("Invoice has no stored before/after comparison")
            if cint(apply) and approved_rows.get(row["erp_invoice"], {}).get("status") not in (
                "local_preflight_passed", "already_synced"
            ):
                frappe.throw("Invoice did not pass the approved dry run")
            result = repair_one(row, bool(cint(apply)), approved_rows.get(row["erp_invoice"]))
            if cint(apply):
                frappe.db.commit()  # One completed ERP/MRP pair at a time.
            results.append(result)
        except Exception as exc:
            frappe.db.rollback()
            results.append({"old_name": row["erp_invoice"], "status": "failed", "error": str(exc),
                            "action": "Stop and inspect; rerun the same manifest to recover any committed ERP amendment."})
            break  # Do not continue altering cumulative withholding after a failure.
    report = {"apply": bool(cint(apply)), "manifest_sha256": manifest_hash,
              "manifest": manifest, "results": results}
    if not cint(apply):
        target = Path(report_file or f"{manifest_file}.dry-run.{time.time_ns()}.json")
        raw = json.dumps(report, indent=2, default=str).encode()
        # Never overwrite a report that may already have been reviewed.
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(raw)
            output.flush()
            os.fsync(output.fileno())
        return {"report_file": str(target.resolve()), "sha256": hashlib.sha256(raw).hexdigest(),
                "apply": False, "results": results}
    return report


def repair_one(row, apply, approved=None):
    if not row.get("mrp_invoice"):
        return repair_erp_only(row, apply)
    if apply:
        frappe.db.get_value("Purchase Invoice", row["mrp_invoice"], "name", for_update=True)
    inv = frappe.get_doc("Purchase Invoice", row["mrp_invoice"])
    inv.check_permission("write")
    if inv.docstatus != 1:
        frappe.throw("MRP invoice must remain submitted")
    marker = f"TDS repair synchronized from {row['erp_invoice']}"
    already_synced = frappe.db.exists("Comment", {
        "reference_doctype": inv.doctype, "reference_name": inv.name,
        "comment_type": "Info", "content": marker,
    })
    if inv.erp_inv_name != row["erp_invoice"] and not already_synced:
        frappe.throw("MRP ERP invoice link changed; refusing to overwrite")
    if (inv.vendor_bill_tracking or None) != (row.get("vendor_bill_tracking") or None):
        frappe.throw("Vendor Bill Tracking differs from the manifest")
    vendor = None
    if inv.vendor_bill_tracking:
        if apply:
            frappe.db.get_value("Vendor Bill Tracking", inv.vendor_bill_tracking, "name", for_update=True)
        vendor = frappe.get_doc("Vendor Bill Tracking", inv.vendor_bill_tracking)
        vendor.check_permission("write")
        if (vendor.docstatus != 1 or vendor.mrp_purchase_invoice != inv.name
                or vendor.purchase_invoice != inv.erp_inv_name or vendor.form_status != "Closed"):
            frappe.throw("Vendor Bill Tracking links/status require review")
    local_state = {
        "mrp": {field: inv.get(field) for field in (
            "name", "modified", "docstatus", "erp_inv_name", "erp_inv_docstatus", "final_amount",
            "due_date", "vendor_bill_tracking",
        )},
        "vendor": {field: vendor.get(field) for field in (
            "name", "modified", "docstatus", "purchase_invoice", "mrp_purchase_invoice", "form_status",
        )} if vendor else None,
    }
    local_state = json.loads(json.dumps(local_state, default=str))
    if apply and not already_synced and (not approved or approved.get("local_state") != local_state):
        frappe.throw("MRP/vendor data differs from the approved dry run; review again")
    if not apply:
        return {"old_name": row["erp_invoice"], "mrp_invoice": inv.name,
                "status": "already_synced" if already_synced else "local_preflight_passed",
                "local_state": local_state}
    res = post_erp_request(ENDPOINT, {
        "erp_invoice": row["erp_invoice"], "mrp_invoice": inv.name, "modified": row["modified"],
        "reviewed": row["comparison"],
        "include_existing": row.get("include_existing", False),
    }, timeout=1800)
    try:
        res.raise_for_status()
    except HTTPError as exc:
        try:
            error = res.json()
            detail = error.get("exception") or error.get("_server_messages") or error.get("exc_type")
        except (ValueError, AttributeError):
            detail = None
        raise RuntimeError(f"ERP repair HTTP {res.status_code}: {detail or 'Request rejected'}") from exc
    result = res.json()["message"]
    if result.get("status") == "skipped":
        if result.get("old_name") != row["erp_invoice"] or result.get("mrp_invoice") != inv.name:
            frappe.throw("Unexpected ERP skip response")
        return result
    if (result["old_name"] != row["erp_invoice"] or result["mrp_invoice"] != inv.name
            or result["docstatus"] != 1 or not result["name"] or not result["withholding_tracked"]
            or (result.get("vendor_bill_tracking") or None) != (inv.vendor_bill_tracking or None)):
        frappe.throw("Unexpected ERP repair response; stop and review")
    if already_synced:
        if inv.erp_inv_name != result["name"]:
            frappe.throw("Previously synchronized amendment does not match ERP")
        return {**result, "status": "already_synced"}
    inv.update({"erp_inv_name": result["name"], "erp_inv_docstatus": result["docstatus"],
                "final_amount": result["amount"], "due_date": result["due_date"]})
    inv.save()  # Normal update-after-submit checks; do not re-bill GRNs/work orders.
    if vendor:
        vendor.reopen_vendor_bill(f"TDS repair: replacing {row['erp_invoice']}")
        vendor.close_vendor_bill(result["name"], f"TDS repair of {row['erp_invoice']}")
        vendor.save()
    inv.add_comment("Info", marker)
    return {**result, "status": "repaired"}


def repair_erp_only(row, apply):
    """Desk invoices have no local synchronization; ERP still validates the snapshot."""
    if row.get("vendor_bill_tracking"):
        frappe.throw("Vendor Bill Tracking without an MRP invoice requires manual review")
    if not apply:
        return {"old_name": row["erp_invoice"], "status": "local_preflight_passed",
                "route": "erp", "local_state": None}
    res = post_erp_request(ENDPOINT, {
        "erp_invoice": row["erp_invoice"], "mrp_invoice": None,
        "modified": row["modified"], "reviewed": row["comparison"],
        "include_existing": row.get("include_existing", False),
    }, timeout=1800)
    res.raise_for_status()
    result = res.json()["message"]
    if result.get("old_name") != row["erp_invoice"] or result.get("mrp_invoice"):
        frappe.throw("Unexpected ERP-only repair response")
    if result.get("status") == "skipped":
        return result
    if (result.get("docstatus") != 1 or not result.get("name")
            or not result.get("withholding_tracked") or result.get("vendor_bill_tracking")):
        frappe.throw("Unexpected ERP-only amendment; stop and review")
    return {**result, "status": "repaired", "route": "erp"}
