import frappe
from frappe.utils import today, add_to_date
from production_api.mrp_stock.report.stock_balance.stock_balance import execute as stock_balance

@frappe.whitelist()
def get_stock(item, warehouse, remove_zero_balance_item=1):
    filters = {
        'from_date': add_to_date(today(), days=-7),
        'to_date': today(),
        'item': item,
        'warehouse': warehouse,
        'remove_zero_balance_item': remove_zero_balance_item
    }
    _, data = stock_balance(filters)
    item_wh_map = {}
    for d in data:
        group_by_key = get_group_by_key(d)
        if group_by_key not in item_wh_map:
            item_wh_map[group_by_key] = frappe._dict(
                {
                    "item": d.item,
                    "warehouse": d.warehouse,
                    "warehouse_name": d.warehouse_name,
                    "bal_qty": 0.0,
                    "uom": d.stock_uom,
                }
            )
        qty_dict = item_wh_map[group_by_key]
        qty_dict.bal_qty += d.bal_qty
    
    return [d for _, d in item_wh_map.items()]

def get_group_by_key(row) -> tuple:
    group_by_key = [row.item, row.warehouse]
    return tuple(group_by_key)