# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
from production_api.mrp_stock.stock_ledger import make_sl_entries
from six import string_types
from production_api.mrp_stock.doctype.stock_entry.stock_entry import get_uom_details
from production_api.production_api.doctype.item_price.item_price import get_item_variant_price
from production_api.mrp_stock.utils import get_stock_balance
from six import string_types

class FGStockEntry(Document):
	
	def before_submit(self):
		self.validate_data()
		self.make_mrp_sle_entries()

	def validate_data(self):
		received_type = frappe.db.get_single_value("Stock Settings","default_received_type")
		for row in self.items:
			if row.rate in ["", None, 0, '0']:
				row.rate = get_stock_balance(
					row.item_variant, None, self.posting_date, self.posting_time, with_valuation_rate=True, uom=row.uom,
				)[1]
				if not row.rate:
					# try if there is a buying price list in default currency
					buying_rate = get_item_variant_price(row.item_variant, variant_uom=row.uom)
					if buying_rate:
						row.rate = buying_rate
			row.received_type = received_type			
	
	def before_cancel(self):
		self.ignore_linked_doctypes = ("Stock Ledger Entry")
		self.make_mrp_sle_entries()

	def make_mrp_sle_entries(self):
		sl_entries = []
		for d in self.items:
			sl_entries.append(frappe._dict({
				"item" : d.get('item_variant'),
				"received_type": d.get('received_type'),
				"warehouse" : self.warehouse,
				"posting_date" : self.get("posting_date"),
				"posting_time" : self.get("posting_time"),
				"recieved_by" : self.get("recieved_by"),
				"qty" :  flt(d.get('stock_qty')),
				"voucher_type" : "FG Stock Entry",
				"voucher_no" : self.get('name'),
				"voucher_detail_no" : d.get('name'),
				"is_cancelled" : 1 if self.get('docstatus') == 2 else 0
			}))
		if self.docstatus == 2:
			sl_entries.reverse()
		make_sle_entries(sl_entries)

def make_sle_entries(sle_details):
	from production_api.api.stock import get_default_fg_lot
	if isinstance(sle_details, string_types):
		sle_details = frappe.json.loads(sle_details)
	default_lot = get_default_fg_lot()
	for d in sle_details:
		d['lot'] = default_lot
	make_sl_entries(sle_details)

@frappe.whitelist()
def create_FG_ste(lot, received_by, supplier, dc_number, warehouse, posting_date, posting_time, items_list, comments, created_user):
	if isinstance(items_list, string_types):
		items_list = frappe.json.loads(items_list)
	
	doc = frappe.new_doc("FG Stock Entry")
	doc.set('lot', lot)
	doc.set('received_by', received_by)
	doc.set('dc_number', dc_number)
	doc.set('supplier', supplier)
	doc.set('warehouse', warehouse)
	doc_items = []
	for i in items_list:
		stock_details = get_uom_details(i['item_variant'], i['uom'], i['qty'])
		doc_items.append({
			"item_variant" : i['item_variant'],
			"qty" : i['qty'],
			"uom" : i['uom'],
			"stock_qty" : flt(
				flt(i['qty'])*flt(stock_details['conversion_factor'])
			),
			"conversion_factor" : flt(stock_details['conversion_factor']),
			"stock_uom" : stock_details['stock_uom'],
			"rate" : 0,
			"row" : i['row'],
			"col" : i['col']
		})
	doc.set('items', doc_items)
	doc.set('posting_date', posting_date)
	doc.set('posting_time', posting_time)
	doc.set('created_sms_user', created_user)
	doc.set("comments", comments)
	doc.save()
	doc.submit()
	return doc.name

def get_stock_entry_detail(stock_entry):

	doc = frappe.get_doc("FG Stock Entry", stock_entry)
	items_list = []
	for i in doc.get('items'):
		item = {
			"item_variant" : i.item_variant,
			"qty" : i.qty,
			"row" : i.row,
			"col" : i.col,
			"uom" : i.uom
		}
		if len(items_list) == 0:
			items_list.append([item])
			continue
		found = False
		for j in items_list:
			if j[0]['row'] == item['row'] and j[0]['col'] == item['col']:
				found = True
				ind = items_list.index(j)
				items_list[ind].append(item)
				break
		if not found :
			items_list.append([item])
	resp =  {
		"stock_entry_name" : doc.name,
		"supplier" : doc.supplier,
		"warehouse" : doc.warehouse,
		"received_by" : doc.received_by,
		"comments" : doc.comments,
		"posting_date" : doc.posting_date,
		"posting_time" : doc.posting_time,
		"user" : doc.created_sms_user,
		"dc_number" : doc.dc_number,
		"lot" : doc.lot,
		"items" : items_list,
		"created_at" : doc.creation
	}
	return resp

def get_inward_stock(item, warehouselist):

	if isinstance(warehouselist, string_types) :
		warehouselist = frappe.json.loads(warehouselist)

	warehouseFilter = "("

	ind = 0
	for i in warehouselist:
		warehouseFilter += f"'{i}'"
		if ind < len(warehouselist)-1:
			warehouseFilter += ','
		ind += 1
	warehouseFilter += ")"

	query = f"""
		SELECT `tabFG Stock Entry Detail`.qty as pending_qty,
		`tabFG Stock Entry Detail`.row as row,
		`tabFG Stock Entry Detail`.col as col,
		`tabFG Stock Entry`.creation as st_entry_date,
		`tabFG Stock Entry`.posting_date as posting_date,
		`tabFG Stock Entry`.posting_time as posting_time,
		`tabFG Stock Entry`.supplier as supplier,
		`tabFG Stock Entry`.warehouse as warehouse,
		`tabFG Stock Entry`.received_by as received_by,
		`tabFG Stock Entry`.lot as lot,
		`tabFG Stock Entry`.dc_number as dc_number,
		`tabFG Stock Entry Detail`.item_variant as item_variant,
		`tabFG Stock Entry Detail`.uom as uom,
		`tabItem Variant`.item as item_name,
		`tabFG Stock Entry`.name as stock_entry
		FROM `tabFG Stock Entry Detail` JOIN  `tabFG Stock Entry` ON `tabFG Stock Entry Detail`.parent = `tabFG Stock Entry`.name
		JOIN `tabItem Variant` ON `tabFG Stock Entry Detail`.item_variant=`tabItem Variant`.name  WHERE `tabItem Variant`.item = '{item}' 
		{ f'AND `tabFG Stock Entry`.warehouse IN  {warehouseFilter}' if len(warehouselist) > 0 else "" }
	"""

	return frappe.db.sql(query, as_dict=True)