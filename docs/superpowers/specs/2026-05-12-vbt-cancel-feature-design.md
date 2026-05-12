# Vendor Bill Tracking — Cancel Feature Hardening

**Date:** 2026-05-12
**Apps touched:** `production_api` (mrp.site), `essdee` (erp15.site)
**Doctype:** Vendor Bill Tracking (VBT)

## Problem

Today the VBT Cancel button is gated to "Accounts Manager / Accounts User" in JS, but only System Manager actually has `cancel` permission in the doctype JSON — inconsistent and effectively unusable for the intended users.

When a linked Purchase Invoice (MRP-side or ERP-side) is cancelled or deleted, the VBT's PI link can be left dangling:

- `production_api.purchase_invoice.before_cancel` clears `VBT.mrp_purchase_invoice` blindly — no check that the VBT actually points at *this* PI — and never restores `form_status`.
- `essdee.utils.mrp.purchase_invoice.vendor_bill_on_cancel` blindly calls `reopen_vendor_bill` on mrp.site — again no match check, and the receiver doesn't verify either.
- Neither side handles **deletion** of a draft PI (which is created with `after_insert` already populating `VBT.mrp_purchase_invoice`).

Result: a VBT can end up reopened or wiped because an unrelated PI was cancelled, and Closed VBTs whose PI was cancelled stay Closed (so the user can't act on them).

## Requirements

1. **Permissions:** HR User and System Manager can cancel a VBT. Other roles cannot.
2. **Cancel button gating:** The Cancel button shows on the VBT form only when:
   - current user has HR User or System Manager role, AND
   - both `purchase_invoice` and `mrp_purchase_invoice` are empty.
3. **MRP PI cancel/delete → VBT revert:** When an MRP Purchase Invoice is cancelled or deleted, clear `VBT.mrp_purchase_invoice` *if and only if* it equals the PI's name. If it doesn't match, skip — never alter another VBT's link.
4. **ERP PI cancel/delete → VBT revert:** Symmetric to #3 for `VBT.purchase_invoice` (driven from essdee on erp15.site, executed by an API call to mrp.site).
5. **Status reopen on revert:** When a link is cleared (#3 or #4), set `form_status = "Reopen"` *only if* it was `Closed`. Other statuses are left untouched (the link clear is enough).
6. **Audit trail:** Every revert appends a row to `vendor_bill_tracking_history` (action `Reopen`, remarks identifying the cancelled/deleted PI and origin side).
7. **Mismatch handling:** Silent skip — write a `frappe.log_error` so it's auditable but don't throw; the PI cancellation/deletion must not be blocked by VBT linkage state.

## Design

### Shared "safe revert" primitive

New whitelisted method on production_api:

```python
# production_api/.../vendor_bill_tracking/vendor_bill_tracking.py

@frappe.whitelist()
def revert_purchase_invoice_link(name, pi_field, expected_pi_name, origin=None):
    """
    Safely clear a PI link on a Vendor Bill Tracking row.

    name              VBT name
    pi_field          "mrp_purchase_invoice" or "purchase_invoice"
    expected_pi_name  Name of the PI that triggered this revert; must equal
                      the current VBT[pi_field] for the clear to happen.
    origin            Optional string (e.g. "MRP-cancel", "ERP-delete") for the
                      history remarks.
    """
```

Behavior:

- Validate `pi_field` ∈ {`"mrp_purchase_invoice"`, `"purchase_invoice"`}; otherwise throw (programming error).
- Load the VBT.
- If `getattr(doc, pi_field) != expected_pi_name`:
  - Call `frappe.log_error` with a clear title (`VBT revert skipped — PI mismatch`) and contextual body (VBT name, field, expected vs actual). Return without changes.
- Else:
  - Clear the field.
  - Append one assignment_detail row: `action="Reopen"`, `assigned_by=frappe.session.user`, `remarks=f"Auto-reverted: {pi_field} {expected_pi_name} {origin or 'cancelled/deleted'}"`.
  - If `form_status == "Closed"` → set `form_status = "Reopen"`.
  - Save with `ignore_permissions=True` (Frappe will bump `modified` and persist the child row append).

### MRP-side wiring (production_api)

`production_api/.../purchase_invoice/purchase_invoice.py`:

- Replace the body of `remove_vendor_bill_purchase_invoce` with a call to `revert_purchase_invoice_link(self.vendor_bill_tracking, "mrp_purchase_invoice", self.name, origin="MRP-cancel")`. (Method kept; callers untouched.)
- Add a new `on_trash` method that calls `revert_purchase_invoice_link(..., origin="MRP-delete")` when `self.vendor_bill_tracking` is set. This handles draft PIs that were auto-linked via `after_insert` and then deleted before submission.

### ERP-side wiring (essdee)

`essdee/essdee/utils/mrp/purchase_invoice.py`:

- `vendor_bill_on_cancel`: change the cross-site call from `reopen_vendor_bill` to `revert_purchase_invoice_link` with `pi_field="purchase_invoice"`, `expected_pi_name=doc.name`, `origin="ERP-cancel"`.
- New `vendor_bill_on_trash`: same call with `origin="ERP-delete"`.
- `essdee/hooks.py` `doc_events["Purchase Invoice"]`: add `"on_trash": "essdee.essdee.utils.mrp.purchase_invoice.vendor_bill_on_trash"`.
- Keep `vendor_bill_on_submit` (close) unchanged.

The legacy whitelisted `reopen_vendor_bill` on production_api is left in place for manual use but is no longer invoked by automated PI lifecycle events.

### Permissions

`vendor_bill_tracking.json` — HR User permblock: add `cancel: 1` (already has `submit: 1`). System Manager already has `cancel: 1`. No other role gets cancel.

### Form JS

`vendor_bill_tracking.js` — change the gate around the existing "Cancel" custom button from
```
if (frappe.user.has_role("Accounts Manager") || frappe.user.has_role("Accounts User"))
```
to
```
const can_cancel = frappe.user.has_role("HR User") || frappe.user.has_role("System Manager");
const both_pi_empty = !frm.doc.purchase_invoice && !frm.doc.mrp_purchase_invoice;
if (can_cancel && both_pi_empty) { /* add Cancel button */ }
```
Other custom buttons (Create MRP PI, Create ERP PI, etc.) keep their existing role gating.

## Flow diagrams

**ERP PI cancel:**

```
User cancels Purchase Invoice on erp15.site
  → essdee Purchase Invoice on_cancel hook
    → vendor_bill_on_cancel
      → POST mrp.site/api/method/...revert_purchase_invoice_link
         {name, pi_field="purchase_invoice", expected_pi_name=doc.name, origin="ERP-cancel"}
        → match? clear field + Reopen-if-Closed + history row
        → no match? log_error, return
```

**MRP PI delete:**

```
User deletes draft Purchase Invoice on mrp.site
  → on_trash
    → revert_purchase_invoice_link(VBT, "mrp_purchase_invoice", self.name, "MRP-delete")
      → match? clear + Reopen-if-Closed + history row
      → no match? log_error, return
```

## Testing

### Unit (test_vendor_bill_tracking.py)

For `revert_purchase_invoice_link`:

- Match + status=Closed → field cleared, status=Reopen, one new history row with action=Reopen.
- Match + status=Open/Assigned/Reopen → field cleared, status unchanged, history row added.
- Mismatch → no changes; one `frappe.log_error` written.
- Invalid `pi_field` → throws.

### Manual cross-site smoke

| Scenario | Setup | Action | Expected |
|---|---|---|---|
| ERP PI cancel reverts | VBT Closed via ERP PI X | Cancel X on erp15.site | VBT.purchase_invoice empty, status Reopen, history row with origin=ERP-cancel |
| ERP PI delete reverts | Draft ERP PI Y linked to VBT | Delete Y | VBT.purchase_invoice empty, no status change if VBT not Closed |
| MRP PI cancel reverts | VBT Closed via MRP PI Z | Cancel Z on mrp.site | VBT.mrp_purchase_invoice empty, status Reopen, history row with origin=MRP-cancel |
| MRP PI delete reverts | Draft MRP PI W linked to VBT | Delete W | VBT.mrp_purchase_invoice empty |
| Mismatch is safe | VBT now points at PI A; cancel old PI B that no longer matches | Cancel B | VBT unchanged, Error Log entry "VBT revert skipped — PI mismatch" |
| Cancel button visibility | VBT with no PIs, HR User | Open form | Cancel button visible |
| Cancel button hidden | VBT with mrp_purchase_invoice set, HR User | Open form | Cancel button NOT visible |
| Role gate | VBT with no PIs, Accounts Manager | Open form | Cancel button NOT visible |

## Out of scope

- Touching the existing `reopen_vendor_bill` / `close_vendor_bill` / `assign_vendor_bill` / `cancel_vendor_bill` whitelisted APIs (left as-is).
- Changing how the ERP PI page is launched from the VBT form (the `erp_mrp_connector` flow).
- Changing the Cancel reason capture dialog (still required; just shown to a different role set).
- Bulk cancel.
