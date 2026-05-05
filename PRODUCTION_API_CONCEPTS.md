# Production API — Conceptual Documentation

A Frappe-based, lot-driven manufacturing execution system (MES) built for apparel and textile production. The system tracks products from order through cutting, sewing, finishing, and dispatch — managing materials, quality, and cost at every stage.

**Publisher**: Essdee
**Modules**: Production Api (core workflow), Essdee Production (lot execution & T&A), MRP Stock (inventory & valuation), Product Development (items & attributes)

---

## Table of Contents

1. [Product Definition](#1-product-definition)
2. [Production Order (PPO)](#2-production-order-ppo)
3. [Lot — The Core Execution Unit](#3-lot--the-core-execution-unit)
4. [Work Order — Process Task Assignment](#4-work-order--process-task-assignment)
5. [Process-Specific Execution](#5-process-specific-execution)
6. [Material Flow — Delivery & Receipt](#6-material-flow--delivery--receipt)
7. [Stock Module (MRP Stock)](#7-stock-module-mrp-stock)
8. [End-to-End Flow](#8-end-to-end-flow)
9. [Key Architectural Concepts](#9-key-architectural-concepts)

---

## 1. Product Definition

### Item — The Product Template

An **Item** is the product master. It defines a product (e.g. "T-Shirt") and its attribute dimensions. Items are not SKUs — they are templates from which concrete variants are generated.

Every Item has:
- A **primary attribute** — the main axis of variation, typically Size.
- An optional **dependent attribute** — a second dimension (e.g. Packing Stage) that controls which other attributes are available at each stage.
- **Additional attributes** — extra dimensions like Colour, Panel, etc.

Each Item gets its own copy of attribute mappings (cloned from global mappings on creation), so attribute values can be customized per product without cross-item interference.

### Item Variant — The Concrete SKU

An **Item Variant** is a specific, manufacture-able product: a particular combination of attribute values. For example, "T-Shirt" (Item) + Size=M + Colour=Blue = one Item Variant.

Variants are created automatically via `get_or_create_variant()` whenever a new attribute combination is needed — during order entry, lot expansion, or BOM calculation. If a variant with those exact attributes already exists, it is reused.

The variant system supports an optional **tuple attribute** optimization: attribute combinations are stored as a sorted tuple string for fast lookup instead of iterating all variants.

### Dependent Attribute — Lifecycle Stage Tracking

The **dependent attribute** is what makes this system apparel-specific. The same physical item changes its variant identity as it progresses through manufacturing stages.

Example: A T-Shirt at the "Cut" stage and the same T-Shirt at the "Sewn" stage are different Item Variants. The dependent attribute (e.g. "Pack") gates which other attributes are valid at each stage. This allows the system to track the same physical goods through production stages using the variant system rather than separate status fields.

A **Dependent Attribute Mapping** defines, for each dependent value (e.g. "Pack", "OutsidePack"), which attributes are allowed. For instance, the "Pack" stage might allow Size and Colour, while "OutsidePack" only allows Size.

### Item Production Detail (IPD) — The Manufacturing Blueprint

The **IPD** is the single source of truth for how an Item is manufactured. It is versioned per item (auto-named as `Item-1`, `Item-2`, etc.), allowing multiple production methods to coexist.

An IPD defines:

- **Process pipeline**: The three core processes — `cutting_process`, `stiching_process`, `packing_process` — each referencing a Process doctype.
- **Packing configuration**: Which attribute to pack by (`packing_attribute`, typically Colour), how many values per pack (`packing_attribute_no`), units per pack (`packing_combo`), and whether quantities distribute evenly (`auto_calculate`) or use custom splits (`packing_attribute_details`).
- **Stitching configuration**: The stitching attribute, in/out stages (dependent attribute values), stitching item details with default quantities, and stitching combinations per major attribute.
- **Set item logic**: For multi-part products (e.g. a suit = jacket + trousers). Controlled by `is_set_item`, with a `major_attribute_value`, `set_item_attribute`, and combination details mapping major attributes to parts and colours.
- **BOM (Bill of Materials)**: Two types:
  - **Fixed BOM**: Quantity calculated as `total_qty / qty_of_product * qty_of_bom_item` regardless of attributes.
  - **Attribute-dependent BOM**: Quantity looked up from an attribute mapping based on the specific variant being produced.
- **Cloth details**: Fabric specifications stored as JSON — `cutting_items_json` maps attribute combinations to weight/dia specs, `cutting_cloths_json` maps combinations to cloth items.
- **Accessory details**: Trims and accessories with their own attribute combinations and cloth type mappings.
- **Embellishment processes**: Optional decorative processes (embroidery, printing) with their own configurations.

The IPD's defaults (which processes, which stages) are initialized from a global **IPD Settings** document.

---

## 2. Production Order (PPO)

The **Production Order** (internally "PPO") is the entry point — it captures customer demand and translates it into manufacturing work.

### What It Contains

- **Item reference**: Which product to produce, with its primary and dependent attributes.
- **Production order details**: A table of Item Variant + quantity + pricing (MRP, wholesale, retail) for each size/variant ordered.
- **Production ordered details**: Tracks which Lots have consumed which quantities from this order — populated automatically as Lots are created and linked.
- **Delivery date and posting date**: Used to calculate `lead_time_given`.
- **Production Term**: A reference to an approved Production Term document (must be submitted) that governs production rules.

### Lifecycle

1. **Draft**: Order details entered, Item Variants auto-created from attribute combinations.
2. **Submitted**: Validates that the Production Term is approved and delivery date is after posting date. Locks in the order. Records `submitted_by` and `submitted_time`.
3. **Lots created**: One or more Lots are created from or linked to the PPO via `create_lot()` or `link_lot()`.
4. **Cannot cancel**: If any Lot references this PPO, cancellation is blocked — the Lots must be dealt with first.

### Variant Auto-Creation

When a PPO is updated, `update_order()` automatically creates any missing Item Variants based on the item details provided. It uses the primary and dependent attributes from the Item to determine the correct variant for each size/colour combination.

---

## 3. Lot — The Core Execution Unit

The **Lot** is where manufacturing actually happens. It represents a production batch — a group of items to be manufactured together through the same process pipeline.

### Creation

Lots are created from a PPO via two mechanisms:
- `create_lot(ppo, lot_name)`: Creates a brand-new Lot linked to the PPO, status "Open".
- `link_lot(ppo, lot_name)`: Links an existing Lot to the PPO.

Multiple Lots can exist per PPO (batch splitting for production efficiency).

### Item Expansion

When a Lot is created or recalculated, `calculate_order()` expands the high-level item quantities into detailed **lot_order_details** using the IPD as a blueprint:

- For **non-set items**: Each item is expanded by packing attribute values. If the packing attribute is Colour with values [Red, Blue, Green], a single size entry becomes three lot_order_detail rows (one per colour), each with its calculated quantity based on the packing combo and UOM conversion factor.
- For **set items**: Expansion crosses the major attribute with set item attributes, creating a variant for every combination of part × colour.

Each lot_order_detail row tracks: `item_variant`, `quantity`, `cut_qty`, `stich_qty`, `pack_qty`, `set_combination`, `row_index`, `table_index`. These quantity fields are updated as work orders progress through the pipeline.

### BOM Calculation

`calculate_order()` also triggers `get_calculated_bom()` from the IPD module, which computes the full bill of materials:

- **Fixed BOM items**: Simple ratio calculation from total quantity.
- **Attribute-dependent BOM items**: Looks up each variant's attributes against the BOM mapping.
- **Cloth requirements**: Calculated from `cutting_items_json` — weight per attribute combination × quantity × stitching multipliers. Grouped by cloth type, colour, and dia.
- **Accessories**: Similar to cloth, with additional stitching dependency lookups.

The result populates the Lot's `bom_summary` table and records `last_calculated_time`.

### Time & Action Tracking

Each Lot has **lot_time_and_action_details** — a schedule of process milestones. `get_time_and_action_process()` queries the next uncompleted action step per Time & Action master, returning action name, department, planned date, rescheduled date, and colour.

### Status

Open → Closed. The Lot's `before_submit()` validates that the BOM summary exists (meaning `calculate_order()` has been run).

---

## 4. Work Order — Process Task Assignment

A **Work Order** assigns a specific manufacturing process (Cutting, Sewing, Packing, or an embellishment process) on a Lot to a Supplier.

### Structure

- **Process reference**: Which manufacturing process this work order covers.
- **Lot reference**: Which production lot.
- **Supplier**: Who performs the work (external supplier or internal unit).
- **Deliverables**: Items going OUT to the supplier — what needs to be processed. Each row tracks `qty`, `pending_qty`, `received_qty`, `delivered_qty`, `cancelled_qty`.
- **Receivables**: Items coming back IN after processing. Each row tracks similar quantity fields plus `billed_qty`.
- **Work order calculated items**: Intermediate BOM items needed for this specific process.
- **Cost**: Calculated from the **Process Cost** doctype using tiered pricing. Rate is looked up by process, item, lot, and supplier, then adjusted for attribute quantity and stitching multipliers.

### Status Chain

The status is dynamically computed from quantity fields:

```
Submitted
  → Partially Delivered (some deliverables sent to supplier)
    → Fully Delivered (all deliverables sent)
      → Partially Received (some receivables returned)
        → Fully Received (all receivables returned)
          → Partially Billed (some receivables billed)
            → Fully Billed (all receivables billed)
              → Closed (manually closed via open_status)
```

### Special Behaviors

**Packing Work Order** (`includes_packing = True`):
On submission, orchestrates cross-lot stock movements if the lot is a transferred lot:
1. Fetches the parent lot's Finishing Plan.
2. Creates a Stock Entry (Material Issue) to reduce stock from the parent lot.
3. Creates a Stock Entry (Material Receipt) to add stock to the packing lot.
4. Updates the Finishing Plan with transferred quantities.
5. Enqueues `create_finishing_doc()` as a background job.
6. A lot can only have one packing work order — duplicates are blocked.

**Internal Unit Work Order** (`is_internal_unit = True`):
On submission, auto-creates a **Sewing Plan** via `create_sewing_plan()` for production monitoring at the internal unit.

**Rework Work Order** (`is_rework = True`):
For rework loops. `update_deliverables()` splits deliverable quantities across GRN items and updates their `rework_quantity` fields.

### Cancellation Guards

A Work Order cannot be cancelled if:
- A submitted Delivery Challan exists against it.
- A submitted GRN exists against it.

On cancellation, linked Finishing Plans are deleted, stock entries reversed, and Sewing Plans removed.

---

## 5. Process-Specific Execution

### Cutting Plan

Created for cutting work orders. Manages the fabric-to-cut-pieces stage.

**What it tracks**:
- **Cloth details**: Required weight vs received weight vs used weight vs balance weight, per cloth item variant.
- **Cut items**: Size × colour combinations to be cut, linked to the lot's order.
- **Cutting LaySheets**: Individual cutting layouts (managed separately).
- **Cut Panel Movements**: Bundle tracking for cut pieces.

**Status progression** (dynamically computed on update):
```
Planned (no fabric received)
  → Fabric Partially Received (some cloth, below required - allowance%)
    → Ready to Cut (sufficient fabric available)
      → Cutting In Progress (has completed layouts)
        → Partially Completed (some colours done)
          → Completed (all colours cut)
```

Fabric receipt updates come from Delivery Challans — when a DC delivers cloth to the cutting location, it updates the cutting plan's cloth weight. The system tracks `no_of_colours_completed` to measure progress.

### Sewing Plan

Auto-created for internal sewing work orders when the work order's process matches the finishing inward process.

**What it tracks**:
- **Sewing Plan Entry Details**: Daily production entries per supplier, date, and work station. Each entry records quantity, input type, and links to a grid of items.
- **Input/output tracking**: Cut pieces in → sewn pieces out, with pre-final and final inspection stages.
- **Daily Production Report (DPR)**: Aggregated data via `get_sewing_plan_dpr_data()` for production monitoring dashboards.

The sewing plan acts as a production journal — supervisors enter daily quantities, and the system aggregates them for status reporting and WO progress tracking.

### Finishing Plan

Auto-created for packing work orders. Manages the final stage: QC, packing, and dispatch.

**What it tracks**:
- **Inward details** (`finishing_plan_details`): Items received from sewing, with accepted, lot-transferred, and ironing excess quantities.
- **QC results** (`finishing_plan_reworked_details`): Reworked and rejected quantities per item.
- **Packed items** (`finishing_plan_grn_details`): Box-packed items ready for dispatch, with dispatched quantity tracking.
- **Dispatch records** (`finishing_plan_dispatch`): Links to dispatch journals/packing slips.

**Key workflows**:

1. **Inward**: Receive sewn pieces. Aggregate accepted + rework + rejected quantities into a colour × size matrix.
2. **QC Gate**: Split into accepted (continue), rework (return to supplier via return GRN), and rejected (scrap/return).
3. **Ironing**: Optional ironing stage with excess quantity tracking.
4. **Packing**: Box items by size into cartons. Validates box quantities match dispatch expectations.
5. **Dispatch**: Create Delivery Challans to ship packed boxes to the customer. Links to FG Stock Entries for finished goods tracking.

`return_items()` creates return GRNs for rejected items. `create_grn()` auto-creates GRNs against the work order with proper received_type splits. `create_delivery_challan()` generates DCs for final dispatch.

---

## 6. Material Flow — Delivery & Receipt

### Delivery Challan (DC)

Transfers materials from one location to another — typically from an internal warehouse to a supplier for processing.

**On submission**:
1. **Reduce stock** at the source location (creates SLEs with qty × -1).
2. **Add stock** at the destination (creates SLEs with qty × +1).
3. **Update work order**: Reduces `pending_qty` on the WO's deliverables.
4. **Update cutting plan**: If applicable, adjusts cloth weights.
5. **Bundle tracking**: Links to Cut Panel Movement, creates Cut Bundle Ledger entries.

**Transfer routing**:
- **Internal unit transfer**: Direct warehouse-to-supplier when `from_address == supplier_address` and `is_internal_unit`.
- **External supplier**: Routes through a **transit warehouse** (configured in Stock Settings). Path: source → transit → supplier.
- **Non-bundle mode**: `allow_non_bundle = True` bypasses cut panel movement tracking. Requires special role authorization.

**On cancellation**: All SLEs are reversed (multipliers flip), WO pending quantities restored, linked stock entries cancelled.

### Goods Received Note (GRN)

Receives materials — either production outputs from suppliers (against Work Order) or raw materials (against Purchase Order).

**Against Work Order** (production GRN):
- Receives processed items back from the supplier.
- `calculate_grn_deliverables()` auto-derives accepted/rework/rejected quantities from cutting or sewing plan records.
- `split_items()` groups received items by `received_type` (default, rework, etc.), creating separate SLE entries per quality tier.
- Creates SLEs: reduce from supplier warehouse, add to internal warehouse.
- Updates WO receivable quantities.

**Against Purchase Order** (raw material GRN):
- Receives fabric, accessories, or other purchased materials.
- Validates `received_qty ≤ pending_qty + tolerance` from the PO.
- Applies freight charges on a per-product basis.

**Return GRN** (`is_return = True`):
- Reverses the flow — returns items to the supplier.
- Creates two SLE sets: reduce from supplier, add to the delivery location.

**Quality gate**: Every GRN enforces the equation `accepted_qty + rework_qty + rejected_qty = received_qty`. Materials are routed based on quality outcome:
- **Accepted**: Flows to next production stage.
- **Rework**: Routed to a separate supplier/process chain via rework work orders.
- **Rejected**: Written off or returned via return GRN.

### Purchase Order

Orders raw materials (fabric, accessories) from suppliers. GRNs can receive against a PO, validating quantities and tracking pending receipts.

---

## 7. Stock Module (MRP Stock)

### The 4-Tuple Inventory Key

Every stock position in the system is uniquely identified by four values:

```
(item_variant, warehouse, lot, received_type)
```

- **item_variant**: The specific SKU (Item Variant).
- **warehouse**: Physical or logical location (supplier name, internal unit, transit warehouse).
- **lot**: The production lot this stock belongs to.
- **received_type**: Quality tier (default, rework, defective, etc.). Falls back to the system default from Stock Settings if not specified.

This 4-tuple is the key for Bins, SLEs, and all stock queries. It means the same item in the same warehouse but from different lots or with different quality grades is tracked independently.

### Stock Ledger Entry (SLE)

Every stock movement creates one or more **Stock Ledger Entries** — an immutable audit log.

Each SLE records:
- The 4-tuple key (item, warehouse, lot, received_type).
- `qty`: Positive for inbound, negative for outbound.
- `posting_datetime`: Precise timestamp for chronological ordering.
- `qty_after_transaction`: Running balance after this entry (maintained by reposting).
- `valuation_rate`: FIFO-based cost per unit.
- `stock_queue`: JSON array of `[qty, rate]` tuples — the FIFO queue for valuation.
- `voucher_type` and `voucher_no`: Links back to the source document (DC, GRN, Stock Entry, etc.).
- `is_cancelled`: Flag set when the source document is cancelled.

**SLE creation pipeline** (`make_sl_entries()`):
1. Normalize: Set default `received_type` if empty.
2. Create the SLE document.
3. Get or create the corresponding Bin.
4. Repost: Recalculate FIFO valuation for all future SLEs of this 4-tuple.
5. Update Bin: Set `actual_qty` from the latest SLE's `qty_after_transaction`.

### FIFO Valuation

The system uses First-In-First-Out valuation via the `update_entries_after` class:

- **Incoming stock** (qty > 0): Appends `[qty, rate]` to the FIFO queue.
- **Outgoing stock** (qty < 0): Pops from the front of the queue until the outgoing quantity is satisfied. The valuation rate is the weighted average of the consumed queue entries.

When a past transaction is cancelled, the system:
1. Marks the SLE as cancelled (`is_cancelled = 1`).
2. Reprocesses all future SLEs for that 4-tuple, rebuilding the FIFO queue without the cancelled entry.
3. Creates a **Repost Item Valuation** document for background reprocessing (runs hourly via scheduled job).

### Bin — Current Stock Position

A **Bin** is the snapshot of current stock for one 4-tuple key.

- `actual_qty`: Current physical quantity, derived from the most recent SLE's `qty_after_transaction`.
- `reserved_qty`: Quantity reserved for dispatch (from Stock Reservation Entries).
- Available quantity = `actual_qty - reserved_qty`.

Bins are created automatically when the first SLE for a new 4-tuple is submitted.

### Stock Entry

A general-purpose stock movement document used for internal transfers and system operations.

**Purpose codes**:
- **Material Issue**: Consume from stock (production consumption).
- **Send to Warehouse**: Transfer between locations.
- **Receive at Warehouse**: Inbound from external.
- **Material Consumed**: Production consumption.
- **Stock Dispatch**: Dispatch to customer.
- **DC Completion / GRN Completion**: Internal entries created by DCs and GRNs for transfer completion.

Each Stock Entry creates SLEs for source warehouse (negative) and/or target warehouse (positive). For variant transformations (e.g. stage changes in packing), the entry can update the dependent attribute value, effectively converting one variant to another in stock.

### FG Stock Entry — Finished Goods

Tracks finished goods inbound from suppliers (post-finishing) and outbound for customer dispatch.

- `consumed = 0` (inbound): Adds stock to warehouse. Used when finished goods arrive from a finishing supplier.
- `consumed = 1` (outbound): Removes stock from warehouse. Used for customer dispatch.

Supports bulk entry with a row/column grid layout and can be created from SMS/mobile via `make_fg_ste_from_sms()`.

### Stock Reservation Entry

Reserves finished goods stock for Packing Slip dispatch without consuming it.

- Created when a Packing Slip is generated for a sales order.
- Reserves quantity in the FG warehouse, updating the Bin's `reserved_qty`.
- Status: Reserved → Partially Delivered → Delivered, as dispatch Stock Entries consume the reservation.

### Stock Reconciliation

Adjusts system stock to match physical count. Creates SLEs with absolute `qty_after_transaction` values (not deltas), then reprocesses future entries with corrected FIFO queues.

---

## 8. End-to-End Flow

```
PPO (Production Order)
 │
 │  define what to produce, quantities by size, delivery dates
 │
 ▼
Lot(s)
 │
 │  expand items by packing attributes, calculate BOM,
 │  set up Time & Action milestones
 │
 ▼
Work Order: Cutting
 │
 │  assign cutting process to supplier
 │
 ├──▶ Cutting Plan
 │       │  allocate fabric, track cutting progress
 │       │  status: Planned → Ready to Cut → In Progress → Completed
 │       │
 │       ▼
 │    DC (deliver cut pieces to sewing supplier)
 │       │  SLE: -qty source, +qty supplier
 │       │  update WO deliverable pending_qty
 │       │
 │       ▼
 │    GRN (receive cut pieces at sewing location)
 │       │  quality split: accepted / rework / rejected
 │       │  SLE: +qty at receiving warehouse
 │
 ▼
Work Order: Sewing
 │
 │  assign sewing process (internal unit or external supplier)
 │
 ├──▶ Sewing Plan (auto-created for internal units)
 │       │  daily input entries, pre-final & final inspection
 │       │
 │       ▼
 │    DC (deliver sewn pieces to finishing)
 │       │
 │       ▼
 │    GRN (receive sewn pieces)
 │       │  quality split again
 │
 ▼
Work Order: Packing
 │
 │  assign packing/finishing process
 │
 ├──▶ Finishing Plan (auto-created)
 │       │  inward: receive sewn pieces
 │       │  QC: accept / rework / reject
 │       │  ironing (optional)
 │       │  box packing by size
 │       │  dispatch: DC to customer
 │       │
 │       ├──▶ Return GRN (rejects back to supplier)
 │       │
 │       └──▶ DC + FG Stock Entry (dispatch to customer)
 │
 ▼
Customer receives finished goods

─── Parallel track ───

Purchase Order (raw materials: fabric, accessories)
 │
 ▼
GRN (receive against PO)
 │
 ▼
Stock available for Cutting Plan allocation
```

**Rework loop**: At any quality gate (GRN or Finishing Plan), rejected/rework items create a rework Work Order → DC to rework supplier → GRN back → re-enter the pipeline.

**Lot transfer**: Lots can be split or merged. When a packing WO references a transferred lot, the system creates stock entries to move inventory from the parent lot to the child lot and updates the Finishing Plan accordingly.

---

## 9. Key Architectural Concepts

### Variant-Driven Design
Everything revolves around Item Variants. A production order specifies variants. Lots expand into variants. Work orders track deliverables and receivables as variants. Stock is held per variant. Even stage transitions (cut → sewn → packed) are modeled as variant changes via the dependent attribute.

### IPD as Master Config
The Item Production Detail is the single source of truth for manufacturing. It defines the process pipeline, BOM, packing rules, cloth specifications, and set item logic. Lots reference an IPD to know how to manufacture. Work orders derive their items from the IPD. BOM calculation is centralized in the IPD module.

### Multi-Supplier Pipeline
Different processes can be assigned to different suppliers. Cutting might go to Supplier A, sewing to an internal unit, and finishing to Supplier B. The DC/GRN mechanism handles material transfer between these locations, with stock tracked independently at each.

### Quality Gates
Quality control happens at two points:
1. **GRN**: Every goods receipt splits quantities into accepted/rework/rejected.
2. **Finishing Plan**: Final QC with accept/rework/reject, plus inspection stages.

Rework items loop back through the pipeline via rework work orders.

### JSON Fields for Flexible Data
Many doctypes store complex, variable-structure data as JSON (cutting combinations, cloth specifications, accessory mappings, item details). This provides flexibility for the highly configurable nature of apparel manufacturing — different items can have completely different attribute structures without schema changes.

### Cost Tracking
Every process has cost tracked through the **Process Cost** doctype with tiered pricing. Work orders calculate receivable rates by looking up the process cost for the specific process/item/lot/supplier combination, adjusted for attribute quantities and stitching multipliers. This flows through to billing status tracking on each work order.

### Lot Isolation
Stock is always scoped to a lot. The 4-tuple key `(item, warehouse, lot, received_type)` means that inventory for different production batches never intermingles. FIFO valuation, bin balances, and reposting all operate within lot boundaries.

### Bundle Tracking
Cut pieces are tracked as bundles through the Cut Panel Movement and Cut Bundle Movement Ledger system. Delivery Challans validate that bundle quantities match item quantities, preventing partial bundle splits and maintaining traceability from fabric to finished garment.

---

## Source Files

| Concept | File |
|---------|------|
| Production Order | `production_api/production_api/doctype/production_order/production_order.py` |
| Item & Variants | `production_api/production_api/doctype/item/item.py` |
| Item Production Detail | `production_api/essdee_production/doctype/item_production_detail/item_production_detail.py` |
| Lot | `production_api/essdee_production/doctype/lot/lot.py` |
| Work Order | `production_api/production_api/doctype/work_order/work_order.py` |
| Cutting Plan | `production_api/production_api/doctype/cutting_plan/cutting_plan.py` |
| Sewing Plan | `production_api/production_api/doctype/sewing_plan/sewing_plan.py` |
| Finishing Plan | `production_api/production_api/doctype/finishing_plan/finishing_plan.py` |
| Delivery Challan | `production_api/production_api/doctype/delivery_challan/delivery_challan.py` |
| Goods Received Note | `production_api/production_api/doctype/goods_received_note/goods_received_note.py` |
| Stock Ledger | `production_api/mrp_stock/stock_ledger.py` |
| Stock API | `production_api/api/stock.py` |
| Hooks | `production_api/hooks.py` |
