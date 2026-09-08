# FG Inward Temp

Historical SMS receipts using the existing Stock Settings connection and warehouse
mapping from FG Stock With Lot. No current-stock reconciliation, quantity caps,
valuation calls or lot substitution.

Required filters: Start Date, End Date, Warehouse. Optional exact-match Lot and
Item combine with AND. There is no Item Variant filter. Legacy identifiers accept text because they
need not exist in current masters. Dates include the entire end day. SQL values
are parameterized and cursor/connection close on failure too.

One row per receipt line and nonzero size slot. Original signed quantities and
separate receipts are preserved. Item/size display values are constructed from
the legacy size tables as in FG Stock With Lot, not matched to current Item
Variant documents. Nonzero slots missing valid size metadata remain
visible as `ITEM [unmapped sizeN]` rather than being silently discarded.

## Field meanings and limitations

- Reference: `stockentrydetails.idstockentry`; lot: `lotnumber`.
- Inward timestamp: `creationdate`, not `dcdate`, matching the reference report.
- Created By: raw `blame_user`, not `receiver`.
- Item and Item Name both use `iteminfo.name`; a separate descriptive field has
  not been established by the reference query.
- Size labels/enabled slots come from `sizerange` and `sizetype`.
- Quantity is Box, following FG Stock With Lot's interpretation.
- Neither supplied table has cancellation status. All matching stored receipts
  are included, with a report notice. Retained cancelled records cannot be
  excluded without a rule identifying them. Deleted records are naturally absent.

## Verification / deployment

From the v15 bench:

```sh
env/bin/python -m unittest production_api.mrp_stock.report.fg_inward_temp.test_fg_inward_temp -v
```

Tests mock database connections. Before release, compare a known date/warehouse
range with the old system and confirm quantity units and cancellation handling.
Source enables the report, but it still requires registration on the designated
site through the usual report reload/migration. No site registration, migration
or live historical query has been run here.
