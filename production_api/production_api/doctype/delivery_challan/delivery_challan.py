# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe,json
from six import string_types
from frappe.utils import flt
from itertools import groupby
from frappe.model.document import Document
from production_api.mrp_stock.utils import get_stock_balance
from production_api.mrp_stock.stock_ledger import make_sl_entries
from production_api.production_api.doctype.item.item import get_attribute_details, get_or_create_variant
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index

class DeliveryChallan(Document):
	def on_cancel(self):
		wo_doc = frappe.get_doc("Work Order",self.work_order)
		for item in self.items:
			for deliverable in wo_doc.deliverables:
				if item.ref_docname == deliverable.name:
					deliverable.pending_quantity += item.delivered_quantity
					item.delivered_quantity = 0
					break

		self.ignore_linked_doctypes = ('Stock Ledger Entry')
		add_sl_entries = []
		reduce_sl_entries = []
		res = get_variant_stock_details()
		for row in self.items:
			if res.get(row.item_variant):
				add_sl_entries.append(self.get_sle_data(row,self.from_location,1,{}))	
				reduce_sl_entries.append(self.get_sle_data(row,self.supplier,-1,{}))
		make_sl_entries(add_sl_entries)
		make_sl_entries(reduce_sl_entries)
		wo_doc.save(ignore_permissions=True)		

	def before_submit(self):
		doc = frappe.get_doc("Work Order", self.work_order)
		for deliverable in doc.deliverables:
			for item in self.items:
				if item.ref_docname == deliverable.name:
					deliverable.pending_quantity ='{0:.3f}'.format(deliverable.pending_quantity - item.get('delivered_quantity'))
					break
		doc.save()
		doc.submit()

		add_sl_entries = []
		reduce_sl_entries = []
		res = get_variant_stock_details()
		for row in self.items:
			if res.get(row.item_variant):
				quantity = get_stock_balance(row.item_variant, self.from_location, with_valuation_rate=False)
				if flt(quantity) < flt(row.qty):
					frappe.throw(f"Required quantity is {row.qty} but stock quantity is {quantity}")
				
				reduce_sl_entries.append(self.get_sle_data(row, self.from_location, -1, {}))
				add_sl_entries.append(self.get_sle_data(row, self.supplier, 1, {}))
		make_sl_entries(add_sl_entries)
		make_sl_entries(reduce_sl_entries)
	
	def before_save(self):
		if self.docstatus == 1:
			return
		
		res = get_variant_stock_details()
		for row in self.items:
			if row.delivered_quantity and res.get(row.item_variant):
				quantity, rate = get_stock_balance(row.item_variant,self.from_location,with_valuation_rate = True)
				if row.delivered_quantity < 0:
					frappe.throw("Only positive")
				if flt(quantity) < flt(row.delivered_quantity):
					frappe.throw(f"Quantity is {row.delivered_quantity} but stock count is {quantity} for item {row.item_variant}")
				row.rate = rate	

		doc = frappe.get_doc("Work Order", self.work_order)
		for deliverable in doc.deliverables:
			for item in self.items:
				if item.ref_docname == deliverable.name and item.get('delivered_quantity'):
					deliverable.valuation_rate = item.get('rate')
					break
		doc.save()		
	
	def onload(self):
		if self.get('items'):
			process = frappe.get_value("Work Order",self.work_order,"process_name")
			deliverable_item_details = fetch_item_details(self.get('items'),process, is_new=False)
			self.set_onload('deliverable_item_details', deliverable_item_details)
	
	def before_validate(self):
		if self.docstatus == 1:
			return
		
		if(self.get('deliverable_item_details')):
			deliverables,stock_value = save_deliverables(self.deliverable_item_details,self.from_location)
			self.set('items',deliverables)
			self.stock_value = stock_value
			self.total_value = stock_value
		
		if self.additional_goods_value:
			self.total_value = self.stock_value + self.additional_goods_value	

	def get_sle_data(self, row, location, multiplier, args):
		sl_dict = frappe._dict(
			{
				"doctype": "Stock Ledger Entry",
				"item": row.item_variant,
				"lot": row.lot,
				"warehouse": location,
				"posting_date": self.posting_date,
				"posting_time": self.posting_time,
				"voucher_type": self.doctype,
				"voucher_no": self.name,
				"voucher_detail_no": row.name,
				"qty": row.delivered_quantity * multiplier,
				"uom": row.uom,
				"is_cancelled": 1 if self.docstatus == 2 else 0,
				"valuation_rate": flt(row.rate, row.precision("rate")),
			}
		)
		sl_dict.update(args)
		return sl_dict

def save_deliverables(item_details, from_location):
	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)
	items = []
	row_index = 0
	stock_value = 0
	for table_index, group in enumerate(item_details):
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				for attr, values in item['values'].items():	
					if values.get('qty') or values.get('delivered_quantity'):
						item_attributes[item.get('primary_attribute')] = attr
						item1 = {}
						variant_name = get_or_create_variant(item_name, item_attributes)
						item1['item_variant'] = variant_name
						item1['lot'] = item.get('lot')
						item1['qty'] = values.get('qty')
						item1['delivered_quantity'] = values.get('delivered_quantity')
						item1['pending_quantity'] = item1['qty'] - item1['delivered_quantity']
						item1['uom'] = item.get('default_uom')
						item1['rate'] = values.get('rate')
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['ref_doctype'] = values.get('ref_doctype')
						item1['ref_docname'] = values.get('ref_docname')
						item1['is_calculated'] = values.get('is_calculated')
						stock = get_stock_value(variant_name,item.get('lot'),from_location)
						item1['stock_value'] = stock
						stock_value += stock
						items.append(item1)		
			else:
				if item['values'].get('default'):
					item1 = {}
					variant_name = get_or_create_variant(item_name, item_attributes)
					item1['item_variant'] = variant_name
					item1['qty'] = item['values']['default'].get('qty')
					item1['lot'] = item.get('lot')
					item1['delivered_quantity'] = item['values']['default'].get('delivered_quantity')
					item1['pending_quantity'] = item1['qty'] - item1['delivered_quantity']
					item1['uom'] = item.get('default_uom')
					item1['rate'] = item['values']['default'].get('rate')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['ref_doctype'] = item['values']['default'].get('ref_doctype')
					item1['ref_docname'] = item['values']['default'].get('ref_docname')
					item1['is_calculated'] = item['values']['default'].get('is_calculated')
					stock = get_stock_value(variant_name,item.get('lot'),from_location)
					item1['stock_value'] = stock
					stock_value += stock
					items.append(item1)		
			row_index += 1	
	return items, stock_value

def fetch_item_details(items,process_name, is_new):
	items = [item.as_dict() for item in items]
	if isinstance(items, string_types):
		items = json.loads(items)
	
	if process_name == "Cutting":
		try:
			items = sorted(items, key=lambda i: i['item_variant'] if i['is_calculated'] else i['row_index'])
		except:
			items = sorted(items, key=lambda i: i['item_variant'])
	else:	
		items = sorted(items, key = lambda i: i['row_index'])

	item_details = []
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'lot': variants[0]['lot'],
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			'values': {},
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'secondary_uom': variants[0]['secondary_uom'] or current_item_attribute_details['secondary_uom'],
			'comments': variants[0]['comments'],
		}

		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_doc("Item Variant", variant['item_variant'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'rate': variant['rate'],
							'ref_doctype':"Work Order Deliverables",
							"is_calculated":variant.is_calculated,
						}
						if is_new:
							item['values'][attr.attribute_value]['qty'] = variant['pending_quantity']
							item['values'][attr.attribute_value]['delivered_quantity'] = 0
							item['values'][attr.attribute_value]['ref_docname'] = variant['name']
						else:
							item['values'][attr.attribute_value]['qty'] = variant['qty']
							item['values'][attr.attribute_value]['delivered_quantity'] = variant['delivered_quantity']							
							item['values'][attr.attribute_value]['ref_docname'] = variant['ref_docname']
						break
		else:
			item['values']['default'] = {
				'rate': variants[0]['rate'],
				"ref_doctype":"Work Order Deliverables",
				"is_calculated":variants[0].is_calculated,
			}
			if is_new:
				item['values']['default']['qty'] = variants[0]['pending_quantity']
				item['values']['default']['delivered_quantity'] = 0
				item['values']['default']['ref_docname'] = variants[0]['name']
			else:
				item['values']['default']['qty'] = variants[0]['qty']
				item['values']['default']['delivered_quantity'] = variants[0]['delivered_quantity']
				item['values']['default']['ref_docname'] = variants[0]['ref_docname']

		index = get_item_group_index(item_details, current_item_attribute_details)

		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details["primary_attribute_values"],
				'dependent_attribute': current_item_attribute_details['dependent_attribute'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	return item_details
			
@frappe.whitelist()
def get_deliverables(work_order):
	doc = frappe.get_doc("Work Order",work_order)
	items = fetch_item_details(doc.deliverables,doc.process_name, is_new=True)	
	return {
		"items":items,
		"supplier":doc.supplier,
		"supplier_address":doc.supplier_address,
	}

def get_stock_value(variant, lot, from_location):
	query_result = frappe.db.sql(
        """ 
			SELECT stock_value, valuation_rate FROM `tabStock Ledger Entry`
			WHERE item = %s AND warehouse = %s and lot = %s ORDER BY posting_date DESC, posting_time DESC LIMIT 1
        """, (variant, from_location, lot), as_dict=True
    )
	if query_result:
		return query_result[0]['stock_value']
	return 0

def get_variant_stock_details():
	result = frappe.db.sql(
		"""
			SELECT `tabItem Variant`.name as variant, `tabItem`.is_stock_item as is_stock FROM `tabItem Variant` JOIN `tabItem` 
			ON `tabItem`.name = `tabItem Variant`.item WHERE `tabItem`.is_stock_item = 1;
		"""
	)		
	res = {}
	for row in result:
		res[row[0]] = row[1]
	return res	 