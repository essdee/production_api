# Supplier Pending Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Supplier Pending Report that groups the selected supplier's pending Work Order quantities by Item, Lot, Colour/Part, and Size while hiding colour/part rows received above 90%.

**Architecture:** Add a dedicated page backend that bulk-loads eligible Work Orders and transforms them through a pure aggregation function. The endpoint returns an already-filtered Item → Lot hierarchy to a new Vue report component, keeping the threshold rule on the server and presentation/loading/copy behavior in the browser.

**Tech Stack:** Frappe 15, Python, Vue 3, JavaScript ES modules, Node test runner, unittest

**Spec:** `docs/superpowers/specs/2026-10-08-supplier-pending-report-design.md`

## Global Constraints

- Supplier and Process are required; no Lot, Item, date-range, or threshold filters.
- Include submitted Work Orders only (`docstatus = 1`) and exclude rework (`is_rework = 0`).
- Resolve the selected Process using the existing `Process Details` parent/group semantics.
- Hide a Colour + Part row only when `received_total > delivered_total * 0.90`; exactly 90% remains visible.
- Exclude rows whose delivered total is zero or negative.
- Remove empty Lots and Items after filtering; totals include visible rows only.
- Difference remains `received - delivered`; date fields and quality colours match the existing Inhouse Quantity Report.
- Show Supplier and Process once in the header; do not render a repeated Supplier table column.
- Do not modify the existing Inhouse Quantity Report or its endpoint.
- Add no new runtime dependencies.

## Review Focus

- Decimal quantities around the 90% boundary must not be rounded before comparison; tests pin 90.00% visible and 90.01% hidden.
- Several Work Orders contributing to one Item/Lot/Colour/Part/Size must aggregate once without duplicate rows; the pure-builder fixture covers this.
- Missing DC or GRN dates must return null dates and a null day difference without crashing; the date test covers this.
- No matching Work Orders or all rows filtered out must return a valid empty response and render the report empty state; backend and response-normalization tests cover both paths.
- A failed or overlapping request must not leave Show Report enabled too early or permanently disabled; the loading-controller test covers start/finish accounting.

---

### Task 1: Pure Pending-Quantity Aggregation

**Files:**
- Create: `production_api/production_api/page/supplier_pending_report/__init__.py`
- Create: `production_api/production_api/page/supplier_pending_report/supplier_pending_report.py`
- Create: `production_api/production_api/page/supplier_pending_report/test_supplier_pending_report.py`

**Interfaces:**
- Consumes: normalized Work Order rows, calculated-item rows, Lot/IPD contexts, variant attribute maps, existing-style quality status maps, and the existing `update_if_string_instance`, `min_date`, and `max_date` helpers.
- Produces: `_row_is_pending(delivered, received) -> bool` and `_build_supplier_pending_items(work_orders, calculated_items, lot_contexts, variant_attributes, quality_statuses) -> list[dict]`.

- [ ] **Step 1: Write the failing strict-boundary test**

Add `test_pending_boundary_is_strict_and_requires_delivered_quantity` with literal expectations:

```python
self.assertTrue(report._row_is_pending(100, 90))
self.assertFalse(report._row_is_pending(100, 90.01))
self.assertFalse(report._row_is_pending(0, 0))
self.assertFalse(report._row_is_pending(-1, 0))
```

- [ ] **Step 2: Run the boundary test and verify RED**

Run from `apps/production_api`:

```bash
../../env/bin/python -m unittest production_api.production_api.page.supplier_pending_report.test_supplier_pending_report.TestSupplierPendingReport.test_pending_boundary_is_strict_and_requires_delivered_quantity
```

Expected: FAIL because `_row_is_pending` is absent.

- [ ] **Step 3: Implement `_row_is_pending(delivered, received) -> bool`**

Use `flt` for numeric normalization. Return true only when delivered is positive and received is less than or equal to 90% of delivered; do not round either input.

- [ ] **Step 4: Run the boundary test and verify GREEN**

Run the command from Step 2. Expected: one passing test.

- [ ] **Step 5: Write failing aggregation tests**

Add focused tests with hand-built fixtures:

- `test_builder_groups_sizes_and_work_orders_into_item_lot_colour_part_rows`: two Work Orders contribute to the same set-item row; assert one Item, one Lot, one Colour/Part row, literal S/M delivered/received/difference values, visible totals, configured size order, quality values, and min/max dates.
- `test_builder_filters_completed_rows_and_cascades_empty_lots_and_items`: one row at exactly 90%, one at 90.01%, one zero-delivered row, a Lot containing only hidden rows, and an Item containing only that empty Lot; assert only the boundary row, its Lot, and its Item remain.
- `test_builder_supports_non_set_items_and_missing_dates`: assert no Part field is required, null dates remain null, and `diff_days` is null.
- `test_builder_aggregates_multiple_work_orders_without_duplicate_rows`: assert repeated source rows change quantities, not row count.

- [ ] **Step 6: Run aggregation tests and verify RED**

```bash
../../env/bin/python -m unittest production_api.production_api.page.supplier_pending_report.test_supplier_pending_report
```

Expected: boundary test passes and aggregation tests fail because `_build_supplier_pending_items` is absent.

- [ ] **Step 7: Implement `_build_supplier_pending_items(...) -> list[dict]`**

Build Item and Lot maps keyed by Work Order `item` and `lot`. Derive Colour, Part, and Size with the same rules as `get_inhouse_qty`; initialize all configured sizes; aggregate quantities and Work Order dates; attach quality status; calculate row totals; apply `_row_is_pending`; cascade empty groups; calculate visible totals; and sort Items, Lots, and Colour/Part rows deterministically.

- [ ] **Step 8: Run the backend test module and verify GREEN**

```bash
../../env/bin/python -m unittest production_api.production_api.page.supplier_pending_report.test_supplier_pending_report
```

Expected: all Task 1 tests pass.

- [ ] **Step 9: Commit Task 1**

```bash
git add production_api/production_api/page/supplier_pending_report
git commit -m "feat: aggregate supplier pending quantities"
```

### Task 2: Bulk Data Loading and Whitelisted Endpoint

**Files:**
- Modify: `production_api/production_api/page/supplier_pending_report/supplier_pending_report.py`
- Modify: `production_api/production_api/page/supplier_pending_report/test_supplier_pending_report.py`

**Interfaces:**
- Consumes: `_build_supplier_pending_items(...)` from Task 1 and existing `get_ipd_primary_values`, `get_variant_attr_details`, and `get_eqi_status` helpers.
- Produces: `_resolve_process_names(process) -> tuple[str, ...]`, `_get_supplier_work_orders(supplier, process_names) -> list[frappe._dict]`, and whitelisted `get_supplier_pending_report(supplier, process) -> dict`.

- [ ] **Step 1: Write failing validation and process-resolution tests**

Add:

- `test_endpoint_requires_supplier`
- `test_endpoint_requires_process`
- `test_process_resolution_matches_existing_parent_group_semantics`

The resolution test uses literal Process Details results and asserts a de-duplicated tuple containing the selected Process and resolved parent names.

- [ ] **Step 2: Run the new tests and verify RED**

```bash
../../env/bin/python -m unittest production_api.production_api.page.supplier_pending_report.test_supplier_pending_report
```

Expected: new tests fail because the endpoint and loaders are absent.

- [ ] **Step 3: Implement validation and `_resolve_process_names(process)`**

Use translated `frappe.throw` messages for missing values. Reproduce the existing `Process Details` lookup semantics without changing `get_process_wo_list`, and return a de-duplicated tuple sorted by Process name so query behavior is deterministic.

- [ ] **Step 4: Write the failing Work Order query contract test**

Add `test_work_order_loader_filters_supplier_submitted_non_rework_and_processes`. Its fake `frappe.get_all` accepts only this filter contract:

```python
{
    "supplier": "SUP-001",
    "docstatus": 1,
    "is_rework": 0,
    "process_name": ["in", ("Cutting", "Panel Cutting")],
}
```

Assert returned fields include name, supplier identity, item, lot, process, and all four DC/GRN dates.

- [ ] **Step 5: Run the query test and verify RED**

Run the test module command from Step 2. Expected: query-contract test fails because `_get_supplier_work_orders` is absent.

- [ ] **Step 6: Implement bulk loaders and `get_supplier_pending_report(supplier, process)`**

The endpoint must:

1. validate inputs and resolve process names;
2. fetch eligible Work Orders in one query;
3. return `{supplier, supplier_name, process, items: []}` immediately when none exist;
4. fetch all calculated items for the Work Order names in one query;
5. cache Lot/IPD context once per Lot and variant attributes once per unique Item Variant;
6. load quality status once for the complete Work Order list;
7. call `_build_supplier_pending_items` and return its hierarchy.

Do not emit `frappe.msgprint` for an empty result.

- [ ] **Step 7: Write failing endpoint orchestration tests**

Add:

- `test_endpoint_returns_stable_empty_response_without_work_orders`
- `test_endpoint_passes_bulk_loaded_inputs_to_builder`
- `test_endpoint_uses_supplier_document_name_for_filter_and_returns_supplier_name`

Assert on returned behavior and loader inputs, not framework internals.

- [ ] **Step 8: Run the backend test module and verify GREEN**

```bash
../../env/bin/python -m unittest production_api.production_api.page.supplier_pending_report.test_supplier_pending_report
```

Expected: all backend tests pass.

- [ ] **Step 9: Compile the backend module**

```bash
../../env/bin/python -m py_compile production_api/production_api/page/supplier_pending_report/supplier_pending_report.py production_api/production_api/page/supplier_pending_report/test_supplier_pending_report.py
```

Expected: exit 0 with no output.

- [ ] **Step 10: Commit Task 2**

```bash
git add production_api/production_api/page/supplier_pending_report
git commit -m "feat: expose supplier pending report endpoint"
```

### Task 3: Supplier Pending Report Vue Interface

**Files:**
- Create: `production_api/public/js/Lot/components/supplier_pending_report_utils.mjs`
- Create: `production_api/public/js/Lot/components/supplier_pending_report_utils.test.mjs`
- Create: `production_api/public/js/Lot/components/SupplierPendingReport.vue`

**Interfaces:**
- Consumes: `get_supplier_pending_report(supplier, process)` from Task 2.
- Produces: `buildSupplierPendingRequest({ supplier, process })`, `normalizeSupplierPendingResponse(response)`, `differenceTone(received, delivered)`, `createLoadingTracker(setLoading)`, and the `SupplierPendingReport` Vue component.

- [ ] **Step 1: Write failing frontend utility tests**

Use Node's built-in test/assert APIs to cover:

- missing Supplier returns `Select a Supplier`;
- missing Process returns `Select a Process`;
- valid inputs return the exact endpoint method and `{supplier, process}` arguments;
- an absent or empty response normalizes to stable metadata and an empty `items` list;
- difference tones are `negative`, `positive`, and `zero` for -1, +1, and 0;
- two starts followed by one finish remain loading, and the final finish clears loading.

- [ ] **Step 2: Run the utility test and verify RED**

```bash
node production_api/public/js/Lot/components/supplier_pending_report_utils.test.mjs
```

Expected: FAIL because the utility module is absent.

- [ ] **Step 3: Implement the frontend utilities**

Keep the module framework-independent so Node can execute the real functions. Normalize missing response fields before the component consumes them. The request method is:

```text
production_api.production_api.page.supplier_pending_report.supplier_pending_report.get_supplier_pending_report
```

- [ ] **Step 4: Run the utility test and verify GREEN**

Run the command from Step 2. Expected: all utility tests pass.

- [ ] **Step 5: Implement `SupplierPendingReport.vue`**

Follow `InhouseQuantity.vue` for Frappe controls, date display, quality legend, difference colours, and Copy-as-image. Implement:

- required Supplier and Process Link controls;
- Show Report with disabled spinner/loading state and `always` cleanup;
- supplier/process report header;
- Item headings containing Lot sections;
- Delivered, Received, and Difference row triplets;
- conditional Part column for set items;
- configured size columns, totals, first/last DC and GRN dates, and day difference;
- visible-only total triplets per Lot/Part;
- Pass/Fail/Hold legend and received-cell quality colouring;
- initial and no-pending empty states;
- Copy button disabled while loading/copying or before results exist.

The component must not repeat Supplier in table rows and must not perform threshold filtering locally.

- [ ] **Step 6: Build the production frontend bundle**

Run from `apps/frappe`:

```bash
node esbuild --apps production_api
```

Expected: exit 0 and `DONE Total Build Time`; unrelated existing compiler warnings must be reported but do not invalidate an otherwise successful build.

- [ ] **Step 7: Re-run frontend tests**

```bash
node production_api/public/js/Lot/components/supplier_pending_report_utils.test.mjs
```

Expected: all tests pass.

- [ ] **Step 8: Commit Task 3**

```bash
git add production_api/public/js/Lot/components/SupplierPendingReport.vue production_api/public/js/Lot/components/supplier_pending_report_utils.mjs production_api/public/js/Lot/components/supplier_pending_report_utils.test.mjs
git commit -m "feat: add supplier pending report interface"
```

### Task 4: Page Registration and Manufacturing Workspace Link

**Files:**
- Create: `production_api/production_api/page/supplier_pending_report/supplier_pending_report.js`
- Create: `production_api/production_api/page/supplier_pending_report/supplier_pending_report.json`
- Modify: `production_api/public/js/Lot/index.js:1-90`
- Modify: `production_api/public/js/vue_plugins.js:16-25,1378-1382`
- Modify: `production_api/essdee_production/workspace/manufacturing/manufacturing.json:207-320`
- Modify: `production_api/production_api/page/supplier_pending_report/test_supplier_pending_report.py`

**Interfaces:**
- Consumes: `SupplierPendingReport.vue` from Task 3.
- Produces: `SupplierPendingReportWrapper`, `frappe.production.ui.SupplierPendingReport`, `/app/supplier-pending-report`, and a Manufacturing → Reports workspace link.

- [ ] **Step 1: Write the failing page-metadata contract test**

Add `test_page_and_workspace_metadata_register_supplier_pending_report`. Load the actual JSON files and assert:

- Page name, page_name, and title equal `supplier-pending-report`, `supplier-pending-report`, and `Supplier Pending Report`;
- module is `Production Api` and standard is `Yes`;
- the Manufacturing workspace contains one Page link whose label is `Supplier Pending Report` and `link_to` is `supplier-pending-report`.

- [ ] **Step 2: Run the metadata test and verify RED**

```bash
../../env/bin/python -m unittest production_api.production_api.page.supplier_pending_report.test_supplier_pending_report.TestSupplierPendingReport.test_page_and_workspace_metadata_register_supplier_pending_report
```

Expected: FAIL because the Page JSON and workspace link do not exist.

- [ ] **Step 3: Add Page JSON, Page JavaScript, wrapper, and global registration**

The page refresh handler instantiates `frappe.production.ui.SupplierPendingReport` once per wrapper. Export/import the wrapper through the existing Lot bundle and register it next to `InhouseQuantity`.

- [ ] **Step 4: Add the Manufacturing workspace link**

Insert the Page link under the Reports card and increment that card's `link_count` from 13 to 14. Do not alter other cards or links.

- [ ] **Step 5: Run metadata and backend tests**

```bash
../../env/bin/python -m unittest production_api.production_api.page.supplier_pending_report.test_supplier_pending_report
```

Expected: all tests pass.

- [ ] **Step 6: Validate JSON and rebuild frontend assets**

```bash
../../env/bin/python -m json.tool production_api/production_api/page/supplier_pending_report/supplier_pending_report.json >/dev/null
../../env/bin/python -m json.tool production_api/essdee_production/workspace/manufacturing/manufacturing.json >/dev/null
```

Then, from `apps/frappe`:

```bash
node esbuild --apps production_api
```

Expected: JSON commands exit 0 and the asset build completes successfully.

- [ ] **Step 7: Commit Task 4**

```bash
git add production_api/production_api/page/supplier_pending_report production_api/public/js/Lot/index.js production_api/public/js/vue_plugins.js production_api/essdee_production/workspace/manufacturing/manufacturing.json
git commit -m "feat: register supplier pending report page"
```

## Final Verification

- [ ] Run focused backend tests:

```bash
../../env/bin/python -m unittest production_api.production_api.page.supplier_pending_report.test_supplier_pending_report
```

- [ ] Run focused frontend tests:

```bash
node production_api/public/js/Lot/components/supplier_pending_report_utils.test.mjs
```

- [ ] Run the production asset build from `apps/frappe`:

```bash
node esbuild --apps production_api
```

- [ ] Run the app test suite from the bench's `sites` directory:

```bash
../env/bin/python ../apps/frappe/frappe/utils/bench_helper.py frappe --site mrp3.site run-tests --app production_api
```

- [ ] Check formatting and scope:

```bash
git diff --check
git status --short
```

- [ ] Manually open `/app/supplier-pending-report` on `mrp3.site`, select a Supplier and Process with known pending Work Orders, and verify the Item → Lot hierarchy, strict 90% row filtering, quality colours, dates, loading state, empty state, and Copy action.
