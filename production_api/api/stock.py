import frappe
from frappe.utils import today, add_to_date
from production_api.mrp_stock.report.stock_balance.stock_balance import execute as stock_balance
from six import string_types

@frappe.whitelist()
def get_stock(item, warehouse, remove_zero_balance_item=1):
    
    if isinstance(warehouse,string_types):
        warehouse = frappe.json.loads(warehouse)
    if isinstance(item,string_types):
        item = frappe.json.loads(item)
        
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
                    "item": d['item'],
                    "bal_qty": 0.0,
                    "uom": d['stock_uom'],
                }
            )
        item_wh_map[group_by_key]['bal_qty'] += d['bal_qty']
    
    return item_wh_map

def get_group_by_key(row) -> str:
    # group_by_key = [row['item'], row['warehouse']]
    # return tuple(group_by_key)
    return row['item']