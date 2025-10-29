import frappe, json
from production_api.mrp_stock.doctype.bin.bin import get_stock_balance_bin
from production_api.mrp_stock.doctype.fg_stock_entry.fg_stock_entry import create_FG_ste,get_stock_entry_detail, fg_stock_entry_cancel
from six import string_types
import math
@frappe.whitelist()
def get_stock(item, warehouse, remove_zero_balance_item=1):
    received_type =frappe.db.get_single_value("Stock Settings", "default_received_type")
    
    if isinstance(warehouse,string_types):
        warehouse = json.loads(warehouse)
    if isinstance(item,string_types):
        item = json.loads(item)

    fg_lot = get_default_fg_lot()
        
    data  = get_stock_balance_bin(
        warehouse,
        fg_lot,
        item,
        received_type,
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
    from production_api.mrp_stock.doctype.stock_entry.stock_entry import get_uom_details
    received_type =frappe.db.get_single_value("Stock Settings", "default_received_type")
    if not packing_slip or not warehouse or not items:
        frappe.throw("Required Details not sent")
    if isinstance(items, string_types):
        items = json.loads(items)
    if len(items) == 0:
        frappe.throw("Please provide Items to make Stock entry")
    fg_lot = get_default_fg_lot()
    if frappe.db.exists("Stock Entry", {
        "packing_slip" : packing_slip,
        "from_warehouse" : warehouse,
        "docstatus" : 1
    }) :
        return frappe.db.get_value("Stock Entry", {
            "packing_slip" : packing_slip,
            "from_warehouse" : warehouse
        }, 'name')

    ste = frappe.new_doc("Stock Entry")
    ste.update({
        'purpose': 'Stock Dispatch',
        'packing_slip': packing_slip,
        'from_warehouse': warehouse,
    })
    index = 0
    received_type =frappe.db.get_single_value("Stock Settings", "default_received_type")

    for item in items:
        
        ste.append("items", {
            'item': item['item'],
            'qty': item['qty'],
            'uom': item['uom'],
            'lot': fg_lot,
            'table_index': index,
            'row_index': index,
            'received_type':received_type,
        })
        index += 1
        
    ste.flags.allow_from_sms = True
    item_details_dict = {}
    for item in items:
        if item['sre'] not in item_details_dict:
            item_details_dict[item['sre']] = {
                "uom_conv_detail" : get_uom_details(item['item'], item['uom'], item['qty']),
                "qty" : 0,
                "uom" : item['uom']
            }
        item_details_dict[item['sre']]['qty'] += item['qty']
    for sre, details in item_details_dict.items():
        sre = frappe.get_doc("Stock Reservation Entry", sre)
        sre.delivered_qty += details['uom_conv_detail']['conversion_factor'] * details['qty']
        sre.db_update()
        sre.update_status()
        sre.update_reserved_stock_in_bin()
    ste.submit()
    for sre, details in item_details_dict.items():
        frappe.db.set_value("Stock Reservation Entry", sre, 'stock_entry', ste.name)
    return ste.name

@frappe.whitelist()
def cancel_dispatch_stock_entry(ste_name):
    ste = frappe.get_doc("Stock Entry", ste_name)
    if ste.purpose != "Stock Dispatch":
        frappe.throw("You cannot cancel other Stock Entries")
    if ste.docstatus == 2:
        return
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
        created_user=fg_ste_req['user'],
        customer=fg_ste_req['customer'],
        consumed=fg_ste_req['consumed']
    )

@frappe.whitelist()
def get_fg_stock_entry_details(stock_entry):
    return get_stock_entry_detail(stock_entry)

@frappe.whitelist()
def get_fg_stock_entry_details_list(pageLength, curr_page):

    list_items = frappe.get_list("FG Stock Entry",
                    fields=['name','posting_date', 'posting_time', 'dc_number', 
                    'lot', 'supplier', 'warehouse', 'received_by', 'comments', 'docstatus', 'customer', 'consumed'], 
                start=((curr_page-1) * pageLength), limit=pageLength, order_by='creation DESC' )
    
    total_pages = frappe.db.count("FG Stock Entry")

    return {
        "rows" : list_items,
        "total_pages" : math.ceil(total_pages/pageLength),
        "total_count" : total_pages,
        "displaying" : len(list_items)
    }

@frappe.whitelist()
def cancel_fg_stock_entry(stock_entry):
    return fg_stock_entry_cancel(stock_entry)

@frappe.whitelist()
def get_reserved_stock(warehouse, item):
    from production_api.mrp_stock.doctype.stock_reservation_entry.stock_reservation_entry import get_reserved_stock_details
    if isinstance(warehouse, string_types):
        warehouse = frappe.json.loads(warehouse)
    if isinstance(item, string_types):
        item = frappe.json.loads(item)
    fg_lot = get_default_fg_lot()
    received_type =frappe.db.get_single_value("Stock Settings", "default_received_type")
    stock_details = get_reserved_stock_details(lot=fg_lot, warehouses=warehouse, items=item, received_type=received_type)
    item_wh_map = {}
    for i in stock_details:
        group_by_key = get_group_by_key(i)
        if group_by_key not in item_wh_map:
            item_wh_map[group_by_key] = {
                "item" : i['item'],
                "bal_qty" : 0.0,
                "uom" : i['uom']
            }
        item_wh_map[group_by_key]['bal_qty'] += i['qty']
    return item_wh_map

@frappe.whitelist()
def get_fg_stock_entry_datewise_inward(start_date, end_date, item, warehouse):
    return get_fg_stock_entry_itemwise_outward_inward(start_date, end_date, item, warehouse, is_inward=True)

@frappe.whitelist()
def get_fg_stock_entry_datewise_outward(start_date, end_date, item, warehouse):
    return get_fg_stock_entry_itemwise_outward_inward(start_date, end_date, item, warehouse, is_inward=False)

def get_fg_stock_entry_itemwise_outward_inward(start_date, end_date, item, warehouse, is_inward = True):

    if isinstance(item, string_types):
        item = json.loads(item)
    if isinstance(warehouse, string_types):
        warehouse = json.loads(warehouse)
    
    query = """
        SELECT SUM(t2.qty) as qty, t2.item_variant, t4.item as item_name FROM
        `tabFG Stock Entry` t1 JOIN `tabFG Stock Entry Detail` t2 ON t2.parent = t1.name
        JOIN `tabSupplier` t3 ON t3.name = t1.warehouse
        JOIN `tabItem Variant` t4 ON t4.name = t2.item_variant
        WHERE t1.docstatus = 1 AND t1.posting_date BETWEEN '{start_date}' AND '{end_date}'
        AND t1.consumed = {consumed}
        AND t1.warehouse IN ({warehouse})
        AND t2.item_variant IN ({item})
        GROUP BY t2.item_variant
    """.format(
        start_date=start_date,
        end_date=end_date,
        warehouse=",".join([f"'{w}'" for w in warehouse]),
        item=",".join([f"'{i}'" for i in item]),
        consumed = 0 if is_inward else 1
    )
    return frappe.db.sql(query, as_dict=True)
