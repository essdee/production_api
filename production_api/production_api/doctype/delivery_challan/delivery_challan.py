# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe,json
from six import string_types
from frappe.model.document import Document
from production_api.mrp_stock.utils import get_stock_balance
from itertools import zip_longest
from itertools import groupby
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index
from production_api.production_api.doctype.item.item import get_variant, create_variant, get_attribute_details


class DeliveryChallan(Document):
	def before_submit(self):
		for row in self.items:
			quantity = get_stock_balance(row.item_variant, self.supplier, with_valuation_rate=False)
			if quantity <= row.qty:
				frappe.throw(f"Required quantity is {row.qty} but stock count is {quantity}")
		
		doc = frappe.get_doc("Work Order", self.work_order)
		for item, work_order_item in zip_longest(self.items, doc.deliverables):
			if item.ref_docname == work_order_item.name:
				work_order_item.pending_quantity ='{0:.3f}'.format(work_order_item.pending_quantity - item.get('delivered_quantity')) 
			else:
				frappe.throw("some conflict")		
		doc.save()
		doc.submit()
	
	def onload(self):
		deliverable_item_details = fetch_item_details(self.get('items'), is_new=False)
		self.set_onload('deliverable_item_details', deliverable_item_details)

	def before_validate(self):
		if(self.get('deliverable_item_details')):
			deliverables = save_deliverables(self.deliverable_item_details)
			self.set('items',deliverables)
	
	def before_save(self):
		for row in self.items:
			quantity,rate = get_stock_balance(row.item_variant,self.supplier,with_valuation_rate = True)
			if row.delivered_quantity < 0:
				frappe.throw("Only positive")
			# if row.delivered_quantity > row.pending_quantity:
			# 	frappe.throw("High amount of product in " + row.item_variant)	
			if quantity <= row.delivered_quantity:
				frappe.throw(f"Quantity is {row.qty} but stock count is {quantity}")
			row.rate = rate	

def save_deliverables(item_details):
	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)
	items = []
	row_index = 0
	for table_index, group in enumerate(item_details):
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				for attr, values in item['values'].items():	
					if values.get('qty') or values.get('delivered_quantity'):
						item_attributes[item.get('primary_attribute')] = attr
						item1 = {}
						variant_name = get_variant(item_name, item_attributes)
						if not variant_name:
							variant1 = create_variant(item_name, item_attributes)
							variant1.insert()
							variant_name = variant1.name
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
						items.append(item1)		
			else:
				if item['values'].get('default'):
					item1 = {}
					variant_name = get_variant(item_name, item_attributes)
					if not variant_name:
						variant1 = create_variant(item_name, item_attributes)
						variant1.insert()
						variant_name = variant1.name
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
					items.append(item1)		
			row_index += 1	
	return items
def fetch_item_details(items, is_new):
	items = [item.as_dict() for item in items]
	if isinstance(items, string_types):
		items = json.loads(items)
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
							'qty': variant['qty'],
							'secondary_qty': variant['secondary_qty'],
							'rate': variant['rate'],
							# 'delivered_quantity':variant['delivered_quantity'] or 0
						}
						if variant.get('delivered_quantity'):
							item['values'][attr.attribute_value]['delivered_quantity'] = variant['delivered_quantity']
						else:
							item['values'][attr.attribute_value]['delivered_quantity'] = 0
						doc = None
						if is_new:	
							doc = frappe.get_doc("Work Order Deliverables", variant['name'])
						else:
							doc = frappe.get_doc("Work Order Deliverables", variant['ref_docname'])

						item['values'][attr.attribute_value]['qty'] = doc.qty
						item['values'][attr.attribute_value]['secondary_qty'] = doc.secondary_qty
						item['values'][attr.attribute_value]['ref_doctype'] = "Work Order Deliverables"
						if is_new:
							item['values'][attr.attribute_value]['ref_docname'] = variant['name']
						else:	
							item['values'][attr.attribute_value]['ref_docname'] = variant['ref_docname']
						break
		else:
			item['values']['default'] = {
				'qty': variants[0]['qty'],
				'secondary_qty': variants[0]['secondary_qty'],
				'rate': variants[0]['rate'],
				# 'delivered_quantity':variants[0]['delivered_quantity'] or 0
			}
			if variants[0].get('delivered_quantity'):
				item['values']['default']['delivered_quantity'] = variants[0]['delivered_quantity']
			else:
				item['values']['default']['delivered_quantity'] = 0
			doc = frappe.get_doc("Work Order Deliverables", variants[0]['ref_docname'])
			item['values']['default']['qty'] = doc.qty
			item['values']['default']['secondary_qty'] = doc.secondary_qty
			item['values']['default']['ref_doctype'] = "Work Order Deliverables"
			item['values']['default']['ref_docname'] = variants[0]['ref_docname']
		index = get_item_group_index(item_details, current_item_attribute_details)

		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	return item_details
			
@frappe.whitelist()
def get_deliverables(work_order):
	doc = frappe.get_doc("Work Order",work_order)
	items = fetch_item_details(doc.deliverables, is_new=True)	
	return items

