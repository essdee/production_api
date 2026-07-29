# Copyright (c) 2026, Essdee and contributors
"""Tests for the cross-bench essdee_yrp transfer on PO-GRNs.

The cross-bench HTTP boundary (post_yrp_request) is mocked; the mrp side
(Material Issue create/submit, flags, on_cancel reversal) runs for real inside
the FrappeTestCase transaction. setUp BINDS to an existing submitted PO-GRN
(site convention) and provisions ample stock at delivery_location so the real
Material Issue submit never hits NegativeStockError. All writes roll back.

Deviation note: in production the create runs in its own HTTP request and
COMMITS the Material Issue + flags before a later cancel request. A single test
transaction cannot commit-then-cancel without leaking real docs, so the
yrp-cancel-failure test asserts the observable both-or-neither contract from the
GRN's side (GRN stays docstatus==1) after the internal frappe.db.rollback();
the finer "MI still submitted" is covered structurally + by the f16 idempotency
tests.
"""
from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from production_api.production_api.doctype.goods_received_note.goods_received_note import (
    create_essdee_yrp_stock_entry,
)

MOCK = "production_api.production_api.doctype.goods_received_note.goods_received_note.post_yrp_request"


def _ok():
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"message": {"ok": True, "stock_entry": "STE-YRP-9",
                                       "duplicate": False, "warehouse": "S-0070"}}
    return m


def _err():
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"message": {"ok": False, "error": "Lot X missing on yrp"}}
    return m


def _cancel_ok():
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"message": {"ok": True, "stock_entry": "STE-YRP-9", "message": "cancelled"}}
    return m


def _cancel_err():
    m = MagicMock()
    m.status_code = 200
    m.json.return_value = {"message": {"ok": False, "error": "yrp cancel blew up"}}
    return m


def _non_json():
    """A 200 response whose body is not JSON: resp.json() raises."""
    m = MagicMock()
    m.status_code = 200
    m.json.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")
    return m


def _is_stock_variant(item_variant):
    item = frappe.db.get_value("Item Variant", item_variant, "item")
    return bool(item and frappe.db.get_value("Item", item, "is_stock_item"))


def _positive_stock_rows(doc):
    """Positive-qty rows that are stock items — the rows the transfer actually moves.
    A Stock Entry rejects non-stock items, so a transferable GRN's positive rows must
    all be stock items (else provisioning/transfer errors, unrelated to row parity)."""
    pos = [r for r in doc.items if flt(r.quantity) > 0]
    return pos if pos and all(_is_stock_variant(r.item_variant) for r in pos) else []


def _find_po_grn():
    for name in frappe.get_all(
        "Goods Received Note",
        filters={"against": "Purchase Order", "docstatus": 1,
                 "essdee_yrp_stock_entry_created": 0},
        order_by="creation desc", limit=80, pluck="name",
    ):
        doc = frappe.get_doc("Goods Received Note", name)
        if doc.get("purchase_invoice_name"):
            continue
        if not doc.delivery_location:
            continue
        if _positive_stock_rows(doc):
            return name
    return None


def _find_multi_row_po_grn():
    """An untransferred submitted PO-GRN with >=2 positive item rows — needed to
    prove the transfer keeps EVERY row (row-count parity), not just the first."""
    for name in frappe.get_all(
        "Goods Received Note",
        filters={"against": "Purchase Order", "docstatus": 1,
                 "essdee_yrp_stock_entry_created": 0},
        order_by="creation desc", limit=80, pluck="name",
    ):
        doc = frappe.get_doc("Goods Received Note", name)
        if doc.get("purchase_invoice_name") or not doc.delivery_location:
            continue
        if len(_positive_stock_rows(doc)) >= 2:
            return name
    return None


def _find_multi_parent_po_grn():
    """An untransferred submitted PO-GRN whose positive rows span >=2 DISTINCT parent
    Items — needed to prove the desk grid renders every row. The group-by-row_index
    collapse only DROPS a row across different parent items (rows of the same parent
    merge into one entry's size grid), so a single-parent multi-row GRN can't expose it."""
    for name in frappe.get_all(
        "Goods Received Note",
        filters={"against": "Purchase Order", "docstatus": 1,
                 "essdee_yrp_stock_entry_created": 0},
        order_by="creation desc", limit=200, pluck="name",
    ):
        doc = frappe.get_doc("Goods Received Note", name)
        if doc.get("purchase_invoice_name") or not doc.delivery_location:
            continue
        pos = _positive_stock_rows(doc)
        if len(pos) < 2:
            continue
        parents = {frappe.db.get_value("Item Variant", r.item_variant, "item") for r in pos}
        if len(parents) >= 2:
            return name
    return None


def _provision(grn_name):
    """Add ample stock at the GRN's delivery_location for each of its item rows so
    the real Material Issue (and the cancel-time GRN inward reversal) cannot go
    negative. Rolled back with the test."""
    doc = frappe.get_doc("Goods Received Note", grn_name)
    rows = []
    for r in doc.items:
        if flt(r.quantity) > 0:
            rows.append({"item": r.item_variant, "lot": r.lot,
                         "qty": flt(r.quantity) + 10000000, "uom": r.uom,
                         "received_type": r.received_type, "rate": 1})
    mr = frappe.new_doc("Stock Entry")
    mr.purpose = "Material Receipt"
    mr.to_warehouse = doc.delivery_location
    mr.set("items", rows)
    mr.flags.allow_from_grn = True
    mr.insert(ignore_permissions=True)
    mr.submit()


class TestEssdeeYrpTransferCreate(FrappeTestCase):
    def setUp(self):
        self.grn = _find_po_grn()
        if not self.grn:
            self.skipTest("No untransferred submitted PO-GRN on site")

    @patch(MOCK)
    def test_success_reduces_flags_and_sends_supplier(self, mock_post):
        _provision(self.grn)
        mock_post.return_value = _ok()
        r = create_essdee_yrp_stock_entry(self.grn)
        self.assertTrue(r["ok"])
        payload = frappe.parse_json(mock_post.call_args.args[1]["payload"])
        grn = frappe.get_doc("Goods Received Note", self.grn)
        self.assertEqual(payload["supplier"], grn.delivery_location)
        self.assertTrue(payload["items"])
        self.assertTrue(all(row.get("lot") for row in payload["items"]))
        self.assertTrue(all(row["received_type"] == "Accepted" for row in payload["items"]))
        self.assertEqual(grn.essdee_yrp_stock_entry_created, 1)
        self.assertEqual(grn.essdee_yrp_stock_entry, "STE-YRP-9")
        self.assertEqual(frappe.get_doc("Stock Entry", grn.mrp_material_issue_ref).docstatus, 1)

    @patch(MOCK)
    def test_multi_row_grn_keeps_every_row_in_one_mi_and_payload(self, mock_post):
        """A GRN with N positive item rows must produce exactly ONE mrp Material
        Issue holding all N rows AND send a payload with all N items — one row per
        (item_variant, lot), never dropped/merged (row-count parity)."""
        grn_name = _find_multi_row_po_grn()
        if not grn_name:
            self.skipTest("No untransferred PO-GRN with >=2 positive rows on site")
        _provision(grn_name)
        mock_post.return_value = _ok()
        grn = frappe.get_doc("Goods Received Note", grn_name)
        positive = [(r.item_variant, r.lot, flt(r.quantity)) for r in grn.items if flt(r.quantity) > 0]
        self.assertGreaterEqual(len(positive), 2)

        r = create_essdee_yrp_stock_entry(grn_name)
        self.assertTrue(r["ok"], r)

        # ONE Material Issue, with a Detail row for EVERY positive GRN row (parity)
        mi = frappe.get_doc("Stock Entry", r["mrp_material_issue"])
        self.assertEqual(len(mi.items), len(positive),
                         "the single Material Issue must hold every positive GRN row")
        self.assertEqual(sorted((i.item, i.lot, flt(i.qty)) for i in mi.items), sorted(positive))

        # the payload POSTed to yrp carries all N rows too (yrp builds ONE SE from them)
        payload = frappe.parse_json(mock_post.call_args.args[1]["payload"])
        self.assertEqual(len(payload["items"]), len(positive),
                         "the yrp payload must carry every positive GRN row")
        self.assertEqual(
            sorted((it["item_variant"], it["lot"], flt(it["qty"])) for it in payload["items"]),
            sorted(positive))

    @patch(MOCK)
    def test_multi_parent_mi_renders_all_rows_in_desk_grid(self, mock_post):
        """DISPLAY parity: the mrp Stock Entry desk form renders its item grid from
        fetch_stock_entry_items(items) — pushed via onload -> __onload.item_details —
        NOT the flat child table. The transfer's Material Issue rows, left with the
        Int-column default row_index=0, collapse by row_index into a single grouped
        entry (built from the first row's parent item), so rows for other parent
        items silently vanish from the form even though the child table is complete.
        Every positive GRN row must surface in the grouped grid."""
        from production_api.mrp_stock.doctype.stock_entry.stock_entry import (
            fetch_stock_entry_items,
        )

        grn_name = _find_multi_parent_po_grn()
        if not grn_name:
            self.skipTest("No untransferred PO-GRN spanning >=2 distinct parent items on site")
        _provision(grn_name)
        mock_post.return_value = _ok()
        grn = frappe.get_doc("Goods Received Note", grn_name)
        positive = [(r.item_variant, r.lot, flt(r.quantity)) for r in grn.items if flt(r.quantity) > 0]

        r = create_essdee_yrp_stock_entry(grn_name)
        self.assertTrue(r["ok"], r)
        mi = frappe.get_doc("Stock Entry", r["mrp_material_issue"])
        self.assertEqual(len(mi.items), len(positive))  # data is complete (never the bug)

        # What the desk Vue grid actually receives on load:
        grouped = fetch_stock_entry_items(mi.get("items"))
        rendered_cells = 0
        rendered_qty = 0.0
        for group in grouped:
            for entry in group.get("items", []):
                for cell in (entry.get("values") or {}).values():
                    if flt((cell or {}).get("qty")):
                        rendered_cells += 1
                        rendered_qty += flt(cell["qty"])
        self.assertEqual(rendered_cells, len(positive),
                         f"desk grid must render every MI row; got {rendered_cells} of {len(positive)}")
        self.assertEqual(rendered_qty, sum(q for _, _, q in positive),
                         "desk grid dropped qty from the Material Issue")

    @patch(MOCK)
    def test_yrp_error_rolls_back_mrp(self, mock_post):
        _provision(self.grn)
        mock_post.return_value = _err()
        with self.assertRaises(frappe.ValidationError):
            create_essdee_yrp_stock_entry(self.grn)
        self.assertFalse(frappe.get_doc("Goods Received Note", self.grn).essdee_yrp_stock_entry_created)
        self.assertFalse(frappe.db.exists("Stock Entry",
            {"against": "Goods Received Note", "against_id": self.grn,
             "purpose": "Material Issue", "docstatus": 1}))

    @patch(MOCK)
    def test_network_failure_rolls_back(self, mock_post):
        _provision(self.grn)
        mock_post.side_effect = requests.exceptions.ConnectionError("refused")
        with self.assertRaises(frappe.ValidationError):
            create_essdee_yrp_stock_entry(self.grn)
        self.assertFalse(frappe.get_doc("Goods Received Note", self.grn).essdee_yrp_stock_entry_created)

    def test_guard_blocks_second_run(self):
        frappe.db.set_value("Goods Received Note", self.grn, "essdee_yrp_stock_entry_created", 1)
        with self.assertRaises(frappe.ValidationError):
            create_essdee_yrp_stock_entry(self.grn)

    def test_blocks_non_po_grn(self):
        wo_grn = frappe.get_all("Goods Received Note",
            filters={"against": "Work Order", "docstatus": 1}, limit=1, pluck="name")
        if not wo_grn:
            self.skipTest("No submitted Work-Order GRN on site")
        with self.assertRaises(frappe.ValidationError):
            create_essdee_yrp_stock_entry(wo_grn[0])

    # --- Issue B: caller must hold GRN write permission before the ignore_permissions issue ---
    @patch(MOCK)
    def test_create_blocked_without_grn_write_permission(self, mock_post):
        # HTTP boundary mocked so the check must gate BEFORE any transfer is attempted.
        mock_post.return_value = _ok()
        _provision(self.grn)
        user = "yrp-noperm@test.local"
        if not frappe.db.exists("User", user):
            frappe.get_doc({"doctype": "User", "email": user, "first_name": "NoPerm",
                            "send_welcome_email": 0}).insert(ignore_permissions=True)
        frappe.set_user(user)
        try:
            with self.assertRaises(frappe.PermissionError):
                create_essdee_yrp_stock_entry(self.grn)
        finally:
            frappe.set_user("Administrator")
        # blocked before any Material Issue was created
        self.assertFalse(frappe.db.exists("Stock Entry",
            {"against": "Goods Received Note", "against_id": self.grn,
             "purpose": "Material Issue", "docstatus": 1}))

    # --- Issue C: a non-JSON / unexpected yrp response rolls back and throws clearly ---
    @patch(MOCK)
    def test_non_json_yrp_response_rolls_back_and_throws(self, mock_post):
        _provision(self.grn)
        mock_post.return_value = _non_json()
        with self.assertRaises(frappe.ValidationError):
            create_essdee_yrp_stock_entry(self.grn)
        self.assertFalse(frappe.get_doc("Goods Received Note", self.grn).essdee_yrp_stock_entry_created)
        self.assertFalse(frappe.db.exists("Stock Entry",
            {"against": "Goods Received Note", "against_id": self.grn,
             "purpose": "Material Issue", "docstatus": 1}))


class TestEssdeeYrpCancel(FrappeTestCase):
    def setUp(self):
        self.grn = _find_po_grn()
        if not self.grn:
            self.skipTest("No untransferred submitted PO-GRN on site")
        # allow cancellation regardless of window / PO-open guards
        frappe.db.set_value("MRP Settings", "MRP Settings", "allow_grn_cancellation", 1)
        _provision(self.grn)

    @patch(MOCK)
    def test_cancel_transferred_grn_reverses_both(self, mock_post):
        mock_post.return_value = _ok()
        create_essdee_yrp_stock_entry(self.grn)
        mi = frappe.db.get_value("Goods Received Note", self.grn, "mrp_material_issue_ref")
        self.assertTrue(mi)
        mock_post.return_value = _cancel_ok()
        frappe.get_doc("Goods Received Note", self.grn).cancel()
        self.assertEqual(frappe.db.get_value("Goods Received Note", self.grn, "docstatus"), 2)
        self.assertEqual(frappe.db.get_value("Stock Entry", mi, "docstatus"), 2)          # MI cancelled
        self.assertFalse(frappe.db.get_value("Goods Received Note", self.grn, "essdee_yrp_stock_entry_created"))

    @patch(MOCK)
    def test_yrp_cancel_failure_blocks_grn_cancel(self, mock_post):
        mock_post.return_value = _ok()
        create_essdee_yrp_stock_entry(self.grn)
        mock_post.return_value = _cancel_err()
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc("Goods Received Note", self.grn).cancel()
        # both-or-neither -> the GRN stays active (the internal rollback undid the flip)
        self.assertEqual(frappe.db.get_value("Goods Received Note", self.grn, "docstatus"), 1)

    # --- Issue C: a non-JSON / unexpected yrp cancel response leaves the GRN docstatus==1 ---
    @patch(MOCK)
    def test_non_json_yrp_cancel_response_keeps_grn_active(self, mock_post):
        mock_post.return_value = _ok()
        create_essdee_yrp_stock_entry(self.grn)
        mock_post.return_value = _non_json()
        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc("Goods Received Note", self.grn).cancel()
        self.assertEqual(frappe.db.get_value("Goods Received Note", self.grn, "docstatus"), 1)


class TestEssdeeYrpNoCopy(FrappeTestCase):
    """Issue E: the three transfer-state fields must be no_copy so Amend/Duplicate
    of a transferred GRN does not carry over the already-transferred state."""

    def test_transfer_fields_are_no_copy(self):
        # meta must reflect the JSON no_copy flags
        frappe.reload_doctype("Goods Received Note")
        name = frappe.get_all("Goods Received Note", limit=1, pluck="name")
        if not name:
            self.skipTest("No Goods Received Note on site")
        doc = frappe.get_doc("Goods Received Note", name[0])
        doc.essdee_yrp_stock_entry_created = 1
        doc.essdee_yrp_stock_entry = "STE-YRP-9"
        doc.mrp_material_issue_ref = "STE-MRP-9"
        # ignore_no_copy=False mirrors Amend/Duplicate, which strip no_copy fields.
        copy = frappe.copy_doc(doc, ignore_no_copy=False)
        self.assertFalse(copy.essdee_yrp_stock_entry_created)
        self.assertFalse(copy.essdee_yrp_stock_entry)
        self.assertFalse(copy.mrp_material_issue_ref)
