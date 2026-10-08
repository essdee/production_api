# Supplier Pending Report Design

**Date:** 2026-10-08
**Status:** Ready for review

## Purpose

Add a new **Supplier Pending Report** that lets a user select a Supplier and a Process, then review only the materially pending Work Order quantities for that supplier. The report must preserve the familiar colour/part/size matrix from the existing Inhouse Quantity Report while grouping the output by Item and Lot.

The report is intended to remove almost-complete work from the user's attention. A colour/part row is therefore excluded when its total received quantity across all sizes is strictly greater than 90% of its total delivered quantity.

## User Experience

Create a standard Frappe page named **Supplier Pending Report** and add it to the Manufacturing workspace's Reports card.

The filter row contains:

- Supplier — required Link to `Supplier`
- Process — required Link to `Process`
- Show Report — disabled with a spinner and loading label while the request is running
- Copy — copies the rendered report as an image, matching the existing Inhouse Quantity Report behavior

The selected supplier and process appear once in the report header. The Supplier column is not repeated inside every table.

Results use this hierarchy:

1. Item
2. Lot
3. Colour and Part rows within the Lot

Each Lot renders the same three-row structure used by the Inhouse Quantity Report:

- Delivered
- Received
- Difference

Each Lot table ends with the existing three-row Delivered, Received, and Difference totals. Set-item totals remain separated by Part; non-set items use one item total. These totals include visible pending rows only.

The table columns are:

- S.No
- Colour
- Part, only for set items
- Type
- one column per primary size, in the Item Production Detail's configured order
- Total
- First Date
- Last Date
- Diff

Received cells retain the existing Pass, Fail, and Hold quality colouring. Difference cells retain the existing negative, positive, and zero colouring. Delivered rows show DC dates; Received rows show GRN dates. Missing dates display `-`.

If no rows qualify, show a clear empty state explaining that no pending quantities were found for the selected Supplier and Process.

## Source Data

The report uses `Work Order` and `Work Order Calculated Item` data.

A Work Order qualifies when all of the following are true:

- `supplier` equals the selected Supplier document name
- `docstatus` is 1
- `is_rework` is 0
- `process_name` is the selected Process or one of the process names resolved through the existing `Process Details` parent relationship

The report groups qualifying calculated items by:

1. Work Order `item`
2. Work Order `lot`
3. derived Colour
4. derived Part for set items
5. primary Size

Colour, Part, Size, set-item behavior, and quality status follow the same Item Production Detail and Item Variant rules already used by `get_inhouse_qty`.

All required Work Orders, calculated items, Item Production Details, variants, and quality details should be fetched in bulk or cached per unique key. The implementation must not call the existing Lot-based endpoint once per Lot.

## Quantity and Pending Rules

For every Item + Lot + Colour + Part group:

1. Sum delivered and received quantities for every size.
2. Sum those size quantities into row-level delivered and received totals.
3. Exclude rows whose delivered total is zero or negative.
4. Exclude the row when:

   `received_total > delivered_total * 0.90`

The comparison is deliberately strict:

- exactly 90% received remains visible
- more than 90% received is hidden
- over-received rows are hidden

After row filtering:

- omit a Lot when it has no visible colour/part rows
- omit an Item when it has no visible Lots
- compute Lot and Item totals from visible rows only

Difference values match the existing report:

`difference = received - delivered`

## Date Rules

Dates are aggregated across the qualifying Work Orders that contribute to a visible Item + Lot + Colour + Part row:

- First Date on Delivered: minimum `first_dc_date`
- Last Date on Delivered: maximum `last_dc_date`
- First Date on Received: minimum `first_grn_date`
- Last Date on Received: maximum `last_grn_date`
- Diff: day difference between the aggregated Last GRN Date and Last DC Date

The existing `min_date`, `max_date`, and date formatting semantics should be reused.

## Backend Contract

Add a whitelisted endpoint dedicated to this report. Its request accepts:

```text
supplier: Supplier document name, required
process: Process document name, required
```

The endpoint validates both values before querying.

The response contains report metadata plus already-filtered nested rows:

```text
supplier
supplier_name
process
items[]
  item
  lots[]
    lot
    is_set_item
    set_attr
    primary_values[]
    rows[]
      colour
      part
      values[size]
        delivered
        received
        difference
        quality
      totals
        delivered
        received
        difference
      dates
        first_dc_date
        last_dc_date
        first_grn_date
        last_grn_date
        diff_days
    totals
```

The API returns an empty `items` list when no Work Orders exist or every row is above the pending threshold. It does not use `frappe.msgprint` for normal empty results.

Items, Lots, and colour/part rows are returned in deterministic order. Size order follows each Lot's Item Production Detail configuration.

## Frontend and Page Registration

Implement the report as a Vue component alongside the existing Lot report components. Add a wrapper export and register it with `frappe.production.ui` using the established `Lot/index.js` and `vue_plugins.js` pattern.

Add a standard Page JSON and Page JavaScript entry for route:

```text
/app/supplier-pending-report
```

Add the page to the Manufacturing workspace under Reports.

The frontend owns presentation, validation messages, loading state, copying, and the empty state. The backend owns all aggregation and threshold filtering so the business rule cannot diverge between clients.

## Error Handling

- Missing Supplier: do not call the endpoint; ask the user to select a Supplier.
- Missing Process: do not call the endpoint; ask the user to select a Process.
- Request in progress: disable Show Report and display its spinner/loading label.
- Backend failure: restore the button and leave a visible error through Frappe's normal request handling.
- Empty result: render the report-specific empty state rather than treating it as an error.

## Testing

Backend tests cover:

- required Supplier and Process validation
- Supplier isolation
- submitted Work Orders only
- rework exclusion
- selected Process and existing `Process Details` parent/group resolution
- grouping by Item, Lot, Colour, Part, and Size
- non-set and set-item attribute handling
- exact 90% remains visible
- greater than 90% is hidden
- zero-delivered rows are excluded
- empty Lot and Item cascading removal
- visible-row totals
- minimum and maximum DC/GRN date aggregation
- date difference calculation
- quality status propagation
- deterministic ordering

Frontend-focused tests cover request validation and loading-state behavior. The production Vue bundle must compile successfully.

## Non-Goals

- No Lot, Item, date-range, or completion-percentage filters in the first version.
- No export format beyond the existing Copy-as-image behavior.
- No changes to the current Inhouse Quantity Report or its endpoint.
- No configurable threshold; the rule is fixed at strictly greater than 90%.

## Acceptance Criteria

The feature is complete when a user can select a Supplier and Process, click Show Report, and see the existing Inhouse-style matrix grouped by Item and Lot, with only colour/part rows whose received total is at or below 90% of delivered. Empty Lots and Items are absent, the Supplier column is removed, totals describe visible rows, dates match existing report semantics, and the report is accessible from the Manufacturing workspace.
