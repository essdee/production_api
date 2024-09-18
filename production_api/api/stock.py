import frappe, json
from frappe.utils import today, add_to_date
from production_api.mrp_stock.report.stock_balance.stock_balance import execute as stock_balance
from six import string_types

@frappe.whitelist()
def get_stock(item, warehouse, remove_zero_balance_item=1):
    
    if isinstance(warehouse,string_types):
        warehouse = json.loads(warehouse)
    if isinstance(item,string_types):
        item = json.loads(item)

    fg_lot = get_default_fg_lot()
        
    filters = {
        'from_date': add_to_date(today(), days=-7),
        'to_date': today(),
        'item': item,
        'warehouse': warehouse,
        'lot': fg_lot,
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

@frappe.whitelist()
def make_dispatch_stock_entry(items, warehouse, packing_slip):
    if not packing_slip or not warehouse or not items:
        frappe.throw("Required Details not sent")
    if isinstance(items, string_types):
        items = json.loads(items)
    if len(items) == 0:
        frappe.throw("Please provide Items to make Stock entry")
    fg_lot = get_default_fg_lot()
    ste = frappe.new_doc("Stock Entry")
    ste.update({
        'purpose': 'Stock Dispatch',
        'packing_slip': packing_slip,
        'from_warehouse': warehouse,
    })
    index = 0
    for item in items:
        ste.append("items", {
            'item': item['item'],
            'qty': item['qty'],
            'uom': item['uom'],
            'lot': fg_lot,
            'table_index': index,
            'row_index': index,
        })
        index += 1
    ste.flags.allow_from_sms = True
    ste.save()
    ste.submit()
    return ste.name

@frappe.whitelist()
def cancel_dispatch_stock_entry(ste_name):
    ste = frappe.get_doc("Stock Entry", ste_name)
    if ste.purpose != "Stock Dispatch":
        frappe.throw("You cannot cancel other Stock Entries")
    ste.cancel()

def get_default_fg_lot(raise_error=True):
    stock_settings = frappe.get_single("Stock Settings")
    if not (fg_lot := stock_settings.default_fg_lot) and raise_error:
        frappe.throw("Please set default FG Lot in settings")
    return fg_lot