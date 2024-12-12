import frappe, json
from production_api.mrp_stock.doctype.bin.bin import get_stock_balance_bin
from production_api.mrp_stock.doctype.fg_stock_entry.fg_stock_entry import create_FG_ste,get_stock_entry_detail
from six import string_types
import math

@frappe.whitelist()
def get_stock(item, warehouse, remove_zero_balance_item=1):
    
    if isinstance(warehouse,string_types):
        warehouse = json.loads(warehouse)
    if isinstance(item,string_types):
        item = json.loads(item)

    fg_lot = get_default_fg_lot()
        
    data  = get_stock_balance_bin(
        warehouse,
        fg_lot,item,
        remove_zero_balance_item
    )

    item_wh_map = {}
    for d in data:
        group_by_key = get_group_by_key(d)
        if group_by_key not in item_wh_map:
            item_wh_map[group_by_key] = frappe._dict(
                {
                    "item": d['item'],
                    "bal_qty": 0.0,
                    "uom": d['uom'],
                }
            )
        item_wh_map[group_by_key]['bal_qty'] += d['bal_qty']
    
    return item_wh_map

def get_group_by_key(row) -> str:
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
        
        sre = frappe.get_doc("Stock Reservation Entry", item['sre'])
        sre.delivered_qty += item['qty']
        
        sre.db_update()
        sre.update_status()
        sre.update_reserved_stock_in_bin()
        
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

@frappe.whitelist()
def create_stock_reservation_entries(
	packing_slip,
	items_details: list[dict] | None = None,
) -> None:
	"""Creates Stock Reservation Entries for Sales Order Items."""
	from production_api.mrp_stock.doctype.stock_reservation_entry.stock_reservation_entry import (
		create_stock_reservation_entries_for_so_items as create_stock_reservation_entries,
	)
	return create_stock_reservation_entries(
		"Packing Slip",
        voucher_no=packing_slip,
		items_details=items_details,
	)
 
@frappe.whitelist()
def cancel_stock_reservation_entries(packing_slip, sre_list=None, notify=True) -> None:
	"""Cancel Stock Reservation Entries for Sales Order Items."""
	from production_api.mrp_stock.doctype.stock_reservation_entry.stock_reservation_entry import (
		cancel_stock_reservation_entries,
	)
	cancel_stock_reservation_entries(
		voucher_type="Packing Slip", voucher_no=packing_slip, sre_list=sre_list, notify=notify
	)
 
@frappe.whitelist()
def update_stock_reservation_entries(packing_slip, item_details):
    
    from production_api.mrp_stock.doctype.stock_reservation_entry.stock_reservation_entry import (
        update_stock_reservation_entries,
    )
    
    if isinstance(item_details,string_types):
        item_details = json.loads(item_details)
    
        
    return update_stock_reservation_entries(
        voucher_type = "Packing Slip",
        voucher_no = packing_slip,
        item_details = item_details
    )

@frappe.whitelist()
def make_fg_ste_from_sms(fg_ste_req):
    if isinstance(fg_ste_req, string_types):
        fg_ste_req = frappe.json.loads(fg_ste_req)
    return create_FG_ste(
        lot=fg_ste_req['lot'],
        received_by=fg_ste_req['received_by'],
        dc_number=fg_ste_req['dc_number'],
        supplier=fg_ste_req['supplier'],
        warehouse=fg_ste_req['warehouse'],
        posting_date=fg_ste_req['posting_date'],
        posting_time=fg_ste_req['posting_time'],
        items_list=fg_ste_req['items'],
        comments=fg_ste_req['comments'],
        created_user=fg_ste_req['user']
    )

@frappe.whitelist()
def get_fg_stock_entry_details(stock_entry):
    return get_stock_entry_detail(stock_entry)

@frappe.whitelist()
def get_fg_stock_entry_details_list(pageLength, curr_page):

    list_items = frappe.get_list("FG Stock Entry",
                    fields=['name','posting_date', 'posting_time', 'dc_number', 
                    'lot', 'supplier', 'warehouse', 'received_by', 'comments'], 
                start=((curr_page-1) * pageLength), limit=pageLength, order_by='name ASC' )
    
    total_pages = frappe.db.count("FG Stock Entry")

    return {
        "rows" : list_items,
        "total_pages" : math.ceil(total_pages/pageLength),
        "total_count" : total_pages,
        "displaying" : len(list_items)
    }