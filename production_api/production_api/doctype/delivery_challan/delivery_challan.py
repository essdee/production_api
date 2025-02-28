# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe,json
from six import string_types
from frappe.utils import flt
from itertools import groupby
from datetime import datetime
from frappe.model.document import Document
from production_api.mrp_stock.utils import get_stock_balance
from production_api.mrp_stock.stock_ledger import make_sl_entries
from production_api.production_api.doctype.item.item import get_attribute_details
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index
from production_api.production_api.logger import get_module_logger

class DeliveryChallan(Document):
	def before_cancel(self):
		if self.is_internal_unit:
			ste_list = frappe.get_list("Stock Entry", filters={
				"against":self.doctype,
				"against_id":self.name,
				"purpose":"DC Completion",
				"docstatus":1,
			}, pluck="name")
			for name in ste_list:
				doc = frappe.get_doc("Stock Entry", name)
				doc.cancel()
	
	def on_cancel(self):
		logger = get_module_logger("delivery_challan")
		logger.debug(f"On Cancel {datetime.now()}")
		wo_doc = frappe.get_doc("Work Order",self.work_order)
		for item in self.items:
			for deliverable in wo_doc.deliverables:
				if item.ref_docname == deliverable.name:
					deliverable.pending_quantity += item.delivered_quantity
					item.delivered_quantity = 0
					break
		logger.debug(f"{self.name} Work Order Deliverables Updated {datetime.now()}")
		self.ignore_linked_doctypes = ('Stock Ledger Entry')
		add_sl_entries = []
		reduce_sl_entries = []
		stock_settings = frappe.get_single("Stock Settings")
		received_type = stock_settings.default_received_type
		transit_warehouse = stock_settings.transit_warehouse
		res = get_variant_stock_details()
		self.total_delivered_qty = 0
		for row in self.items:
			if res.get(row.item_variant):
				add_sl_entries.append(self.get_sle_data(row, self.from_location, 1, {}, received_type))	
				supplier = transit_warehouse if self.is_internal_unit else self.supplier
				reduce_sl_entries.append(self.get_sle_data(row, supplier, -1, {}, received_type))
		logger.debug(f"{self.name} SLE data construction {datetime.now()}")
		make_sl_entries(add_sl_entries)
		logger.debug(f"{self.name} Stock Added to From Location {datetime.now()}")
		make_sl_entries(reduce_sl_entries)
		logger.debug(f"{self.name} Stock reduced From Supplier {datetime.now()}")
		wo_doc.save()		

	def on_submit(self):
		wo_doc = frappe.get_cached_doc("Work Order", self.work_order)
		if not wo_doc.first_dc_date:
			wo_doc.first_dc_date = self.posting_date
			wo_doc.last_dc_date = self.posting_date
		else:
			wo_doc.last_dc_date = self.posting_date
		wo_doc.save()			

	def before_submit(self):
		self.letter_head = frappe.db.get_single_value("MRP Settings","dc_grn_letter_head")
		logger = get_module_logger("delivery_challan")
		logger.debug(f"On Submit {datetime.now()}")
		add_sl_entries = []
		reduce_sl_entries = []
		res = get_variant_stock_details()
		stock_settings = frappe.get_single("Stock Settings")
		received_type = stock_settings.default_received_type
		transit_warehouse = stock_settings.transit_warehouse
		total_delivered = flt(0)
		for row in self.items:
			if res.get(row.item_variant):
				quantity, rate = get_stock_balance(row.item_variant, self.from_location,received_type, with_valuation_rate=True, lot=self.lot)
				if flt(quantity) < flt(row.delivered_quantity):
					frappe.throw(f"Required quantity is {row.delivered_quantity} but stock quantity is {quantity} for {row.item_variant}")
				row.rate = rate	
				total_delivered += row.delivered_quantity	
				reduce_sl_entries.append(self.get_sle_data(row, self.from_location, -1, {}, received_type))
				supplier = transit_warehouse if self.is_internal_unit else self.supplier
				add_sl_entries.append(self.get_sle_data(row, supplier, 1, {}, received_type))
		self.total_delivered_qty = total_delivered
		logger.debug(f"{self.name} Stock check and SLE data construction {datetime.now()}")
		wo_doc = frappe.get_cached_doc("Work Order", self.work_order)
		for deliverable in wo_doc.deliverables:
			for item in self.items:
				if item.ref_docname == deliverable.name:
					deliverable.pending_quantity ='{0:.3f}'.format(deliverable.pending_quantity - item.get('delivered_quantity'))
					if item.get('delivered_quantity'):
						deliverable.valuation_rate = item.get('rate')
					break
		wo_doc.save()
		logger.debug(f"{self.name} Work Order deliverables updated {datetime.now()}")
		make_sl_entries(reduce_sl_entries)
		logger.debug(f"{self.name} Stock reduced from From Location {datetime.now()}")
		make_sl_entries(add_sl_entries)
		logger.debug(f"{self.name} Stock Added to Supplier {datetime.now()}")
	
	def before_save(self):
		if self.docstatus == 1:
			return
		for row in self.items:
			if row.delivered_quantity:
				if row.delivered_quantity < 0:
					frappe.throw("Only positive")
	
	def onload(self):
		if self.get('items'):
			deliverable_item_details = fetch_item_details(self.get('items'), self.production_detail,self.lot,is_new=False)
			self.set_onload('deliverable_item_details', deliverable_item_details)
	
	def before_validate(self):
		if self.docstatus == 1:
			return
		
		if(self.get('deliverable_item_details')):
			deliverables,stock_value = save_deliverables(self.deliverable_item_details,self.from_location, self.production_detail)
			self.set('items',deliverables)
			self.stock_value = stock_value
			self.total_value = stock_value
		
		if self.additional_goods_value:
			self.total_value = self.stock_value + self.additional_goods_value	

	def get_sle_data(self, row, location, multiplier, args, received_type):
		sl_dict = frappe._dict({
			"doctype": "Stock Ledger Entry",
			"item": row.item_variant,
			"lot": row.lot,
			"warehouse": location,
			"received_type":received_type,
			"posting_date": self.posting_date,
			"posting_time": self.posting_time,
			"voucher_type": self.doctype,
			"voucher_no": self.name,
			"voucher_detail_no": row.name,
			"qty": row.delivered_quantity * multiplier,
			"uom": row.uom,
			"is_cancelled": 1 if self.docstatus == 2 else 0,
			"rate": flt(row.rate, row.precision("rate")),
			"valuation_rate": flt(row.rate, row.precision("rate")),
		})
		sl_dict.update(args)
		return sl_dict

def save_deliverables(item_details, from_location, ipd):
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_or_create_ipd_variant
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	item_variants = ipd_doc.variants_json
	if isinstance(item_variants, string_types):
		item_variants = json.loads(item_variants)
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
						tup = tuple(sorted(item_attributes.items()))
						variant_name = get_or_create_ipd_variant(item_variants, item_name, tup, item_attributes)
						str_tup = str(tup)
						if item_variants and item_variants.get(item_name):
							if not item_variants[item_name].get(str_tup):
								item_variants[item_name][str_tup] = variant_name	
						else:	
							if not item_variants:
								item_variants = {}
								item_variants[item_name] = {}
								item_variants[item_name][str_tup] = variant_name
							else:
								item_variants[item_name] = {}
								item_variants[item_name][str_tup] = variant_name
						item1['item_variant'] = variant_name
						item1['lot'] = item.get('lot')
						item1['qty'] = values.get('qty')
						item1['secondary_qty'] = values.get('secondary_qty')
						item1['secondary_uom'] = values.get('secondary_uom')						
						item1['delivered_quantity'] = values.get('delivered_quantity')
						item1['pending_quantity'] = item1['qty'] - item1['delivered_quantity']
						item1['uom'] = item.get('default_uom')
						item1['rate'] = values.get('rate')
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['ref_doctype'] = values.get('ref_doctype')
						item1['ref_docname'] = values.get('ref_docname')
						item1['is_calculated'] = values.get('is_calculated')
						item1['set_combination'] = values.get('set_combination', {})
						stock = get_stock_value(variant_name, item.get('lot'), from_location)
						item1['stock_value'] = stock
						stock_value += stock
						items.append(item1)		
			else:
				if item['values'].get('default'):
					item1 = {}
					tup = tuple(sorted(item_attributes.items()))
					variant_name = get_or_create_ipd_variant(item_variants, item_name, tup, item_attributes)
					str_tup = str(tup)
					if item_variants and item_variants.get(item_name):
						if not item_variants[item_name].get(str_tup):
							item_variants[item_name][str_tup] = variant_name	
					else:	
						if not item_variants:
							item_variants = {}
							item_variants[item_name] = {}
							item_variants[item_name][str_tup] = variant_name
						else:
							item_variants[item_name] = {}
							item_variants[item_name][str_tup] = variant_name
					item1['item_variant'] = variant_name
					item1['qty'] = item['values']['default'].get('qty')
					item1['secondary_qty'] = item['values']['default'].get('secondary_qty')
					item1['secondary_uom'] = item['values']['default'].get('secondary_uom')
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
					item1['set_combination'] = item['values']['default'].get('set_combination', {})
					stock = get_stock_value(variant_name,item.get('lot'),from_location)
					item1['stock_value'] = stock
					stock_value += stock
					items.append(item1)		
			row_index += 1	
	ipd_doc.db_set("variants_json", json.dumps(item_variants), update_modified=False)		
	return items, stock_value

def fetch_item_details(items, ipd, lot, is_new=False):
	items = [item.as_dict() for item in items]
	if isinstance(items, string_types):
		items = json.loads(items)

	items = sorted(items, key = lambda i: i['row_index'])
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	item_details = []
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'lot': variants[0]['lot'],
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			"item_keys": {},
			"is_set_item": ipd_doc.is_set_item,
			"set_attr": ipd_doc.set_item_attribute,
			"pack_attr": ipd_doc.packing_attribute,
			"major_attr_value": ipd_doc.major_attribute_value,
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
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				set_combination = variant['set_combination']
				if isinstance(set_combination, string_types):
					set_combination = json.loads(set_combination)
				if set_combination:
					if set_combination.get("major_part"):
						item['item_keys']['major_part'] = set_combination.get("major_part")

					if set_combination.get("major_colour"):
						item['item_keys']['major_colour'] = set_combination.get("major_colour")		

				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'rate': variant['rate'],
							'ref_doctype':"Work Order Deliverables",
							"is_calculated":variant.is_calculated,
							'set_combination':variant.set_combination,
						}
						if is_new:
							item['values'][attr.attribute_value]['qty'] = variant['pending_quantity']
							item['values'][attr.attribute_value]['delivered_quantity'] = 0
							item['values'][attr.attribute_value]['ref_docname'] = variant['name']
						else:
							item['values'][attr.attribute_value]['qty'] = variant['qty']
							item['values'][attr.attribute_value]['secondary_uom'] = variant['secondary_uom']
							item['values'][attr.attribute_value]['secondary_qty'] = variant['secondary_qty']
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
				item['values']['default']['secondary_uom'] = variants[0]['secondary_uom']
				item['values']['default']['secondary_qty'] = variants[0]['secondary_qty']
				item['values']['default']['delivered_quantity'] = variants[0]['delivered_quantity']
				item['values']['default']['ref_docname'] = variants[0]['ref_docname']

		index = get_item_group_index(item_details, current_item_attribute_details)

		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				"lot":lot,
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
	doc = frappe.get_cached_doc("Work Order",work_order)
	items = fetch_item_details(doc.deliverables, doc.production_detail, doc.lot, is_new=True)	
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

@frappe.whitelist()
def get_dc_structure(doc_name):
	doc = frappe.get_doc("Delivery Challan", doc_name)
	item_details = fetch_item_details(doc.items, doc.production_detail, doc.lot)
	return item_details

@frappe.whitelist()
def get_current_user_time():
	d = datetime.now()
	d = datetime.fromtimestamp(d.timestamp()).strftime("%c")
	return [frappe.session.user, d]

@frappe.whitelist()
def get_calculated_items(doc_name,work_order):
	from production_api.production_api.doctype.work_order.work_order import fetch_order_item_details
	doc = frappe.get_doc("Work Order", work_order)
	items = fetch_order_item_details(doc.work_order_calculated_items, doc.production_detail)
	return items

@frappe.whitelist()
def get_calculated_deliverables(items,wo_name, doc_name, deliverable):
	from production_api.production_api.doctype.work_order.work_order import get_deliverable_receivable
	logger = get_module_logger("delivery_challan")
	logger.debug(f"{doc_name} Deliverable Calculation Started {datetime.now()}")
	items = get_deliverable_receivable(items, wo_name, deliverable=deliverable)
	logger.debug(f"{doc_name} Deliverables Calculated {datetime.now()}")
	doc = frappe.get_doc("Delivery Challan", doc_name)
	from itertools import zip_longest
	for item1, item2 in zip_longest(doc.items, items):
		item1.delivered_quantity = item2['qty']
		item1.set_combination = item2.get('set_combination', {})
	doc.save()

@frappe.whitelist()
def construct_stock_entry_details(doc_name):
	doc = frappe.get_doc("Delivery Challan", doc_name)
	stock_settings = frappe.get_single("Stock Settings")
	received_type = stock_settings.default_received_type
	items = []
	for item in doc.items:
		if item.delivered_quantity - item.ste_delivered_quantity > 0:
			items.append({
				"item": item.item_variant,
				"lot": item.lot,
				"qty": item.delivered_quantity - item.ste_delivered_quantity,
				"uom": item.uom,
				"received_type": received_type,
				"secondary_qty": item.secondary_qty,
				"secondary_uom": item.secondary_uom,
				"against_id_detail": item.name,
				"table_index": item.table_index,
				"row_index": item.row_index,
				"remarks": item.comments,
				"set_combination": item.set_combination,
			})
	ste = frappe.new_doc("Stock Entry")
	ste.purpose = "DC Completion"
	ste.against = "Delivery Challan"
	ste.against_id = doc_name
	ste.from_warehouse = doc.from_location
	ste.to_warehouse = doc.supplier
	ste.set("items", items)
	ste.flags.allow_from_dc = True
	ste.save()
	return ste.name
