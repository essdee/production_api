# Vendor Bill Tracking — Cancel Feature Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make VBT cancel work reliably end-to-end: (1) HR User + System Manager can cancel; (2) Cancel button only appears when both PI links are empty; (3) cancel/delete of either MRP PI or ERP PI safely reverts the corresponding link on the VBT with a name-match guard and conditional reopen.

**Architecture:** Add one shared whitelisted primitive `revert_purchase_invoice_link(name, pi_field, expected_pi_name, origin)` on `production_api` (mrp.site). MRP PI lifecycle hooks call it locally; ERP PI lifecycle hooks in `essdee` (erp15.site) call it cross-site via the existing `make_post_request(get_mrp_credentials(), ...)` plumbing. The doctype JSON gets one new `cancel` permission flag, and the form JS swaps role gating on the existing Cancel button.

**Tech Stack:** Frappe (Python + Frappe ORM, JSON doctype perms, vanilla JS form scripts), pytest-style `FrappeTestCase`, cross-site HTTP via `frappe.integrations.utils.make_post_request`.

**Sites involved:** `mrp.site` (production_api) and `erp15.site` (essdee). Both will need `bench --site <X> migrate` once per memory rule "Always migrate all sites that have the modified app installed".

**Commit policy:** Per user memory, commits land at meaningful milestones, not per-task. Three commit points are marked below.

---

## File Map

**production_api (mrp.site):**
- Modify: `production_api/production_api/doctype/vendor_bill_tracking/vendor_bill_tracking.py` — add `revert_purchase_invoice_link` whitelisted function.
- Modify: `production_api/production_api/doctype/vendor_bill_tracking/test_vendor_bill_tracking.py` — add unit tests.
- Modify: `production_api/production_api/doctype/vendor_bill_tracking/vendor_bill_tracking.json` — add `cancel: 1` to HR User perm row.
- Modify: `production_api/production_api/doctype/vendor_bill_tracking/vendor_bill_tracking.js` — split Cancel button out of the Accounts Manager/User block; gate by HR User/System Manager.
- Modify: `production_api/production_api/doctype/purchase_invoice/purchase_invoice.py` — replace body of `remove_vendor_bill_purchase_invoce`; add `on_trash`.

**essdee (erp15.site):**
- Modify: `essdee/essdee/utils/mrp/purchase_invoice.py` — change `vendor_bill_on_cancel` to call the new API; add `vendor_bill_on_trash`; extend existing `on_trash` to call it.
- Modify: `essdee/hooks.py` — no structural change needed (existing `on_trash` and `on_cancel` entries already wired); we chain new functions via the existing handlers.

---

## Task 1: Add `revert_purchase_invoice_link` API + unit tests

**Files:**
- Modify: `/home/sakthi/frappe-bench/apps/production_api/production_api/production_api/doctype/vendor_bill_tracking/vendor_bill_tracking.py`
- Modify: `/home/sakthi/frappe-bench/apps/production_api/production_api/production_api/doctype/vendor_bill_tracking/test_vendor_bill_tracking.py`

### Step 1.1 — Write the failing tests

- [ ] Replace the contents of `test_vendor_bill_tracking.py` with the test class below. The tests cover: invalid field arg, mismatch (no-op + Error Log entry), match with Closed status (clears + reopens + history row), match with non-Closed status (clears only + history row).

```python
# Copyright (c) 2025, Aerele Technologies Pvt Ltd and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking import (
	revert_purchase_invoice_link,
)


def _make_vbt(pi_field, pi_value, form_status):
	"""Create a submitted VBT with a given PI field pre-populated and a given form_status.

	We bypass the normal close flow (which would require a real PI doc) by writing
	the fields directly with frappe.db.set_value after submit.
	"""
	supplier = frappe.db.get_value("Supplier", {}, "name") or frappe.get_doc({
		"doctype": "Supplier",
		"supplier_name": "VBT-Test-Supplier",
		"supplier_group": frappe.db.get_value("Supplier Group", {}, "name"),
	}).insert(ignore_permissions=True).name

	doc = frappe.get_doc({
		"doctype": "Vendor Bill Tracking",
		"supplier": supplier,
		"bill_no": frappe.generate_hash(length=8),
		"bill_date": frappe.utils.today(),
		"invoice_value": 100,
		"received_date": frappe.utils.today(),
		"received_via": "HO",
	})
	doc.insert(ignore_permissions=True)
	doc.submit()
	frappe.db.set_value("Vendor Bill Tracking", doc.name, {
		pi_field: pi_value,
		"form_status": form_status,
	}, update_modified=False)
	return frappe.get_doc("Vendor Bill Tracking", doc.name)


class TestVendorBillTracking(FrappeTestCase):
	def test_revert_invalid_field_raises(self):
		with self.assertRaises(frappe.ValidationError):
			revert_purchase_invoice_link("nonexistent", "bogus_field", "PI-X")

	def test_revert_mismatch_is_noop_and_logs(self):
		vbt = _make_vbt("mrp_purchase_invoice", "PI-REAL", "Closed")
		before_logs = frappe.db.count("Error Log")
		revert_purchase_invoice_link(vbt.name, "mrp_purchase_invoice", "PI-OTHER", origin="MRP-cancel")
		vbt.reload()
		self.assertEqual(vbt.mrp_purchase_invoice, "PI-REAL")
		self.assertEqual(vbt.form_status, "Closed")
		self.assertGreater(frappe.db.count("Error Log"), before_logs)

	def test_revert_match_closed_clears_and_reopens(self):
		vbt = _make_vbt("mrp_purchase_invoice", "PI-MATCH", "Closed")
		history_before = len(vbt.vendor_bill_tracking_history)
		revert_purchase_invoice_link(vbt.name, "mrp_purchase_invoice", "PI-MATCH", origin="MRP-cancel")
		vbt.reload()
		self.assertFalse(vbt.mrp_purchase_invoice)
		self.assertEqual(vbt.form_status, "Reopen")
		self.assertEqual(len(vbt.vendor_bill_tracking_history), history_before + 1)
		last = vbt.vendor_bill_tracking_history[-1]
		self.assertEqual(last.action, "Reopen")
		self.assertIn("MRP-cancel", last.remarks or "")
		self.assertIn("PI-MATCH", last.remarks or "")

	def test_revert_match_non_closed_clears_but_keeps_status(self):
		vbt = _make_vbt("purchase_invoice", "PI-ERP-1", "Open")
		revert_purchase_invoice_link(vbt.name, "purchase_invoice", "PI-ERP-1", origin="ERP-delete")
		vbt.reload()
		self.assertFalse(vbt.purchase_invoice)
		self.assertEqual(vbt.form_status, "Open")
		last = vbt.vendor_bill_tracking_history[-1]
		self.assertEqual(last.action, "Reopen")
		self.assertIn("ERP-delete", last.remarks or "")
```

### Step 1.2 — Run tests to confirm they fail

Run:
```bash
cd /home/sakthi/frappe-bench && bench --site mrp.site run-tests --app production_api --module production_api.production_api.doctype.vendor_bill_tracking.test_vendor_bill_tracking
```
Expected: All four tests fail with `ImportError: cannot import name 'revert_purchase_invoice_link'` (or `AttributeError`).

### Step 1.3 — Implement `revert_purchase_invoice_link`

- [ ] Append the function below to `vendor_bill_tracking.py` (place it just after `reopen_vendor_bill`, before `cancel_vendor_bill`).

```python
@frappe.whitelist()
def revert_purchase_invoice_link(name, pi_field, expected_pi_name, origin=None):
	"""Safely clear a PI link on a Vendor Bill Tracking row.

	Only clears the field if VBT[pi_field] equals expected_pi_name. If they
	differ, the call is silently skipped and an Error Log entry is written for
	audit. On a successful clear, a history row is appended (action="Reopen")
	and form_status is set to "Reopen" only if it was "Closed".
	"""
	allowed_fields = {"mrp_purchase_invoice", "purchase_invoice"}
	if pi_field not in allowed_fields:
		frappe.throw(f"Invalid pi_field: {pi_field}")

	doc = frappe.get_doc("Vendor Bill Tracking", name)
	current = doc.get(pi_field)
	if current != expected_pi_name:
		frappe.log_error(
			title="VBT revert skipped — PI mismatch",
			message=(
				f"VBT: {name}\n"
				f"Field: {pi_field}\n"
				f"Expected: {expected_pi_name}\n"
				f"Actual: {current}\n"
				f"Origin: {origin}"
			),
		)
		return

	doc.set(pi_field, None)
	doc.append("vendor_bill_tracking_history", {
		"assigned_to": doc.assigned_to,
		"assigned_on": frappe.utils.now_datetime(),
		"assigned_by": frappe.session.user,
		"remarks": f"Auto-reverted: {pi_field}={expected_pi_name} ({origin or 'cancelled/deleted'})",
		"action": "Reopen",
	})
	if doc.form_status == "Closed":
		doc.form_status = "Reopen"
	doc.save(ignore_permissions=True)
```

### Step 1.4 — Run tests to confirm they pass

Run the same `bench run-tests` command as Step 1.2. Expected: 4 tests pass.

If a test fails on supplier creation because Supplier Group is empty, create one inline in the helper (`frappe.get_doc({"doctype": "Supplier Group", "supplier_group_name": "Test"}).insert(ignore_permissions=True)`) and re-run.

---

## Task 2: Wire MRP-side Purchase Invoice cancel + delete

**Files:**
- Modify: `/home/sakthi/frappe-bench/apps/production_api/production_api/production_api/doctype/purchase_invoice/purchase_invoice.py`

### Step 2.1 — Replace `remove_vendor_bill_purchase_invoce` body

- [ ] Replace lines 145-147 (the existing `remove_vendor_bill_purchase_invoce` method) with the version below.

```python
	def remove_vendor_bill_purchase_invoce(self, origin="MRP-cancel"):
		from production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking import (
			revert_purchase_invoice_link,
		)
		revert_purchase_invoice_link(
			self.vendor_bill_tracking,
			"mrp_purchase_invoice",
			self.name,
			origin=origin,
		)
```

The existing call site at line 168-169 (`if self.vendor_bill_tracking: self.remove_vendor_bill_purchase_invoce()`) stays unchanged — it will now pass through the new safe primitive.

### Step 2.2 — Add `on_trash` hook on the controller

- [ ] Insert the method below into the `PurchaseInvoice` controller class, after `before_cancel` (right after the existing block ending around line 173).

```python
	def on_trash(self):
		if self.vendor_bill_tracking:
			self.remove_vendor_bill_purchase_invoce(origin="MRP-delete")
```

### Step 2.3 — Manual smoke (one path, fastest)

Run:
```bash
cd /home/sakthi/frappe-bench && bench --site mrp.site console
```
Then in the console:
```python
import frappe
# pick a Closed VBT that has an mrp_purchase_invoice already, OR set one up:
vbt = frappe.get_doc("Vendor Bill Tracking", "<a Closed VBT name>")
print(vbt.mrp_purchase_invoice, vbt.form_status)
pi = frappe.get_doc("Purchase Invoice", vbt.mrp_purchase_invoice)
pi.cancel()
vbt.reload()
print(vbt.mrp_purchase_invoice, vbt.form_status)  # expect: None, "Reopen"
```
Expected: VBT.mrp_purchase_invoice is now empty and form_status == "Reopen".

If you do not have a Closed VBT handy, skip this step — the unit tests in Task 1 plus the cross-site test plan in Task 5 cover the same paths.

---

## Task 3: Wire ERP-side (essdee) cancel + delete

> **Pre-flight (per essdee/CLAUDE.md GitNexus rules):** before editing, run `gitnexus_impact({target: "vendor_bill_on_cancel", direction: "upstream"})` and `gitnexus_impact({target: "on_trash", direction: "upstream"})` and surface any HIGH/CRITICAL warnings. Do not skip.

**Files:**
- Modify: `/home/sakthi/frappe-bench/apps/essdee/essdee/essdee/utils/mrp/purchase_invoice.py`

### Step 3.1 — Replace `vendor_bill_on_cancel`

- [ ] Replace the existing `vendor_bill_on_cancel` function (lines 223-235) with the version below. The function name and signature stay the same so the hooks.py entry needs no change.

```python
def vendor_bill_on_cancel(doc, event):
	if not doc.vendor_bill_tracking or event != 'on_cancel':
		return
	_call_mrp_revert(doc, origin="ERP-cancel")


def _call_mrp_revert(doc, origin):
	cred = get_mrp_credentials()
	resp = make_post_request(
		cred['url'] + "/api/method/production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.revert_purchase_invoice_link",
		cred['credentials'], data={
			"name": doc.vendor_bill_tracking,
			"pi_field": "purchase_invoice",
			"expected_pi_name": doc.name,
			"origin": origin,
		}
	)
	if not resp.ok:
		frappe.log_error("Error Happened In Vendor Bill Tracking Revert", resp.text)
		frappe.throw("Error Happened In Vendor Bill Tracking Revert")
```

### Step 3.2 — Extend the existing `on_trash` to revert ERP-direct PIs

- [ ] Replace the existing `on_trash` (lines 249-252) with the version below. The function preserves the "block MRP-originated PI deletion" behavior and adds VBT revert for ERP-direct PIs.

```python
def on_trash(doc, event):
	if event != "on_trash":
		return
	if doc.get('mrp_purchase_invoice_name'):
		frappe.throw("You can not delete this document.")
	if doc.get('vendor_bill_tracking'):
		_call_mrp_revert(doc, origin="ERP-delete")
```

(No change to `hooks.py` — the on_trash hook is already registered.)

---

## Task 4: VBT permissions + form JS

**Files:**
- Modify: `/home/sakthi/frappe-bench/apps/production_api/production_api/production_api/doctype/vendor_bill_tracking/vendor_bill_tracking.json`
- Modify: `/home/sakthi/frappe-bench/apps/production_api/production_api/production_api/doctype/vendor_bill_tracking/vendor_bill_tracking.js`

### Step 4.1 — Grant cancel to HR User in the doctype JSON

- [ ] In `vendor_bill_tracking.json`, locate the HR User permission block (around line 240-251) and add `"cancel": 1,` alphabetically (between `create` and `email`). The block must end up like:

```json
  {
   "cancel": 1,
   "create": 1,
   "email": 1,
   "export": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "HR User",
   "share": 1,
   "submit": 1,
   "write": 1
  },
```

### Step 4.2 — Move Cancel button out of the Accounts block in form JS

- [ ] In `vendor_bill_tracking.js`, replace lines 26-60 (the block starting `if (!frm.doc.purchase_invoice && !frm.doc.mrp_purchase_invoice) {`) with the version below. The two PI-creation buttons stay gated by Accounts Manager/User; the Cancel button is gated by HR User/System Manager.

```javascript
			if (!frm.doc.purchase_invoice && !frm.doc.mrp_purchase_invoice) {
				if (frappe.user.has_role("HR User") || frappe.user.has_role("System Manager")) {
					frm.add_custom_button(__("Cancel"), () => {
						get_remarks_and_cancel(frm);
					});
				}
				if (frappe.user.has_role("Accounts Manager") || frappe.user.has_role("Accounts User")) {
					frm.add_custom_button(__("Create MRP PI"), () => {
						let x = frappe.model.get_new_doc("Purchase Invoice");
						x.supplier = frm.doc.supplier;
						x.bill_date = frm.doc.bill_date;
						x.bill_no = frm.doc.bill_no;
						x.vendor_bill_tracking = frm.doc.name;
						frappe.set_route("Form", x.doctype, x.name);
					});
					frm.add_custom_button(__("Create ERP PI"), () => {
						frappe.call({
							method:"production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.get_accounting_system_purchase_invoice",
							args: {
								doc_name: frm.doc.name,
							},
							callback: (r) => {
								const defaults = {
									supplier: r.message.supplier,
									bill_no: r.message.bill_no,
									bill_date: r.message.bill_date,
									doctype: r.message.doctype,
									vendor_bill_tracking: r.message.vendor_bill_tracking,
									action: "new",
								};
								const params = new URLSearchParams(defaults).toString();
								window.open(`${r.message.url}/app/erp-mrp-connector?${params}`);
							},
						});
					});
				}
			}
```

---

## ✦ Commit milestone 1 — production_api changes

- [ ] Stage and commit production_api edits only (no push, per user memory).

```bash
cd /home/sakthi/frappe-bench/apps/production_api && git add \
  production_api/production_api/doctype/vendor_bill_tracking/vendor_bill_tracking.py \
  production_api/production_api/doctype/vendor_bill_tracking/test_vendor_bill_tracking.py \
  production_api/production_api/doctype/vendor_bill_tracking/vendor_bill_tracking.json \
  production_api/production_api/doctype/vendor_bill_tracking/vendor_bill_tracking.js \
  production_api/production_api/doctype/purchase_invoice/purchase_invoice.py \
  docs/superpowers/specs/2026-05-12-vbt-cancel-feature-design.md \
  docs/superpowers/plans/2026-05-12-vbt-cancel-feature.md && \
git commit -m "$(cat <<'EOF'
feat(vbt): safe PI link revert + HR User cancel

Add revert_purchase_invoice_link API with name-match guard. MRP PI
before_cancel/on_trash now route through it. Cancel button on VBT
form now visible to HR User + System Manager when both PI fields
are empty.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

## ✦ Commit milestone 2 — essdee changes

- [ ] Stage and commit essdee edits.

```bash
cd /home/sakthi/frappe-bench/apps/essdee && git add \
  essdee/essdee/utils/mrp/purchase_invoice.py && \
git commit -m "$(cat <<'EOF'
feat(mrp-pi): revert VBT link via match-guarded API on cancel/trash

vendor_bill_on_cancel and on_trash now call mrp.site's
revert_purchase_invoice_link with expected_pi_name=doc.name so a
mismatch is silently skipped instead of clearing the wrong VBT.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

Then per essdee/CLAUDE.md: `cd /home/sakthi/frappe-bench/apps/essdee && npx gitnexus analyze --embeddings` if a previous index existed (`cat .gitnexus/meta.json | grep embeddings` to check first).

---

## Task 5: Cross-site smoke test

> Per user memory: "Always migrate all sites that have the modified app installed."

### Step 5.1 — Migrate both sites

Run (one at a time; do not retry on benign tail noise per memory):
```bash
cd /home/sakthi/frappe-bench && bench --site mrp.site migrate
cd /home/sakthi/frappe-bench && bench --site erp15.site migrate
```

### Step 5.2 — Manual cross-site test matrix

Run through each row; mark with ✓ when verified.

| # | Setup | Action | Expected on VBT (mrp.site) |
|---|---|---|---|
| 1 | VBT Closed via ERP PI X | Cancel X on erp15.site | `purchase_invoice` empty, `form_status="Reopen"`, new history row "Auto-reverted: purchase_invoice=X (ERP-cancel)" |
| 2 | Draft ERP PI Y linked to VBT | Delete Y | `purchase_invoice` empty; status unchanged if it wasn't Closed |
| 3 | VBT Closed via MRP PI Z | Cancel Z on mrp.site | `mrp_purchase_invoice` empty, `form_status="Reopen"`, new history row "...MRP-cancel" |
| 4 | Draft MRP PI W linked to VBT | Delete W | `mrp_purchase_invoice` empty |
| 5 | Tamper: set VBT.mrp_purchase_invoice to "PI-OTHER" then cancel the originally-linked PI | Cancel the original PI | VBT unchanged; one new Error Log entry titled "VBT revert skipped — PI mismatch" |
| 6 | Open VBT (no PIs), logged in as HR User | Open VBT form | Cancel button visible; Create MRP PI / Create ERP PI not visible |
| 7 | VBT with `mrp_purchase_invoice` set, HR User | Open VBT form | Cancel button NOT visible |
| 8 | VBT (no PIs), logged in as Accounts Manager | Open VBT form | Cancel button NOT visible; Create buttons visible |

### Step 5.3 — Sanity check Error Log for unexpected entries

Run on mrp.site:
```bash
bench --site mrp.site console
```
Then:
```python
import frappe
for r in frappe.get_all("Error Log", filters={"creation": [">", frappe.utils.add_to_date(None, hours=-1)]}, fields=["name","method","creation"], limit=20):
    print(r)
```

Only entries titled "VBT revert skipped — PI mismatch" from row 5 are expected. Anything else needs investigation.

---

## ✦ Commit milestone 3 — (optional) docs only

If smoke testing exposes anything that needs documenting (e.g., a new caveat), update the spec and amend the docs commit. Otherwise nothing further to commit.

---

## Self-Review

**Spec coverage (one row per spec requirement):**

| Spec requirement | Covered by |
|---|---|
| HR User + System Manager can cancel | Task 4 Step 4.1 (JSON), Task 4 Step 4.2 (JS) |
| Cancel button shows only when both PIs empty | Task 4 Step 4.2 (existing `!purchase_invoice && !mrp_purchase_invoice` check preserved; role gate moved inside) |
| MRP PI cancel → safe revert | Task 2 Step 2.1 (rewires `remove_vendor_bill_purchase_invoce`) |
| MRP PI delete → safe revert | Task 2 Step 2.2 (`on_trash`) |
| ERP PI cancel → safe revert | Task 3 Step 3.1 |
| ERP PI delete → safe revert | Task 3 Step 3.2 |
| Name-match guard, silent skip + log on mismatch | Task 1 Step 1.3 |
| Reopen only if Closed | Task 1 Step 1.3 (`if doc.form_status == "Closed"`) |
| Audit history row on every revert | Task 1 Step 1.3 (`doc.append("vendor_bill_tracking_history", ...)`) |
| Unit test: invalid field | Task 1 Step 1.1 `test_revert_invalid_field_raises` |
| Unit test: mismatch no-op | Task 1 Step 1.1 `test_revert_mismatch_is_noop_and_logs` |
| Unit test: match + Closed | Task 1 Step 1.1 `test_revert_match_closed_clears_and_reopens` |
| Unit test: match + non-Closed | Task 1 Step 1.1 `test_revert_match_non_closed_clears_but_keeps_status` |
| Cross-site smoke matrix | Task 5 Step 5.2 |

No gaps.

**Placeholder scan:** No "TBD"/"TODO"/"implement later" left. All code blocks are complete.

**Type/name consistency:**
- `revert_purchase_invoice_link(name, pi_field, expected_pi_name, origin=None)` — same signature used in Task 1 (definition), Task 2 (MRP caller), Task 3 (ERP caller), and Task 1 (tests). ✓
- `_call_mrp_revert(doc, origin)` defined once in Task 3 Step 3.1, used in Task 3 Step 3.2. ✓
- `pi_field` allowlist `{"mrp_purchase_invoice", "purchase_invoice"}` matches the actual field names on the VBT doctype. ✓
- `frappe.log_error(title=..., message=...)` — correct kwarg names for current Frappe. ✓

---

## Execution

Plan complete and saved to `/home/sakthi/frappe-bench/apps/production_api/docs/superpowers/plans/2026-05-12-vbt-cancel-feature.md`. Two execution options:

1. **Subagent-Driven (recommended)** — Fresh subagent per task, review between tasks.
2. **Inline Execution** — Execute tasks in this session with checkpoints.

Which approach?
