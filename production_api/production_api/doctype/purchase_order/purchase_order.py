# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import throw, _
from frappe.utils import money_in_words
import json, copy
from six import string_types
from itertools import groupby
from jinja2 import TemplateSyntaxError
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_variant, create_variant, get_attribute_details
from production_api.production_api.doctype.item_price.item_price import get_active_price
from production_api.production_api.util import send_notification

class PurchaseOrder(Document):
	def onload(self):
		print('in onload')
		item_details = fetch_item_details(self.get('items'))
		self.set('print_item_details', json.dumps(item_details))
		self.set_onload('item_details', item_details)

	def before_submit(self):
		# print(self.workflow_state)
		print("before submit called")
		price_validation = frappe.db.get_single_value('MRP Settings', 'enable_price_validation')
		try:
			items = validate_price_details([d.as_dict() for d in self.items], self.supplier)
			# print(json.dumps(items, indent=3))
			self.set('items', items)
		except:
			if price_validation:
				raise
		for item in self.items:
			item.set('pending_qty', item.qty)
			item.set('cancelled_qty', 0)
		self.calculate_amount()
		self.set_status()
		self.set('approved_by', frappe.get_user().doc.name)

	def before_update_after_submit(self):
		self.set_status()
	
	def before_cancel(self):
		self.set_status()

	def before_validate(self):
		print(self.item_details)
		if(self.item_details):
			items = save_item_details(self.item_details)
			try:
				items = validate_price_details(items, self.supplier)
			except:
				pass
			print(json.dumps(items, indent=3))
			self.set('items', items)
			self.calculate_amount()
		else:
			frappe.throw('Add items to Purchase Order.', title='Purchase Order')

	def calculate_amount(self):
		total_amount = 0
		total_tax = 0
		grand_total = 0
		for item in self.items:
			item_total = item.rate * item.qty
			total_amount += item_total
			tax = item_total * (float(item.tax or 0) / 100)
			total_tax += tax
			total = item_total + tax
			grand_total += total
		self.set('total', total_amount)
		self.set('total_tax', total_tax)
		self.set('grand_total', grand_total)
		self.set('in_words', money_in_words(grand_total))
	
	def set_status(self):
		if (self.docstatus == 0):
			self.status = "Draft"
		if (self.docstatus == 2):
			self.status = "Cancelled"
		if (self.docstatus == 1):
			self.status = "Ordered"
			self.status = self.get_fulfillment_status()

	def get_fulfillment_status(self):
		# Check for partial and complete fulfillment
		partial = False
		complete = True
		cancelled = False
		for item in self.items:
			if item.pending_qty > 0:
				complete = False
				if item.pending_qty < item.qty:
					partial = True
			elif item.cancelled_qty > 0:
				cancelled = True
		if cancelled:
			return "Partially Cancelled"
		if complete:
			return "Delivered"
		elif partial:
			return "Partially Delivered"
		else:
			return "Ordered"

def validate_price_details(items, supplier):
	item_list = get_unique_items(items)
	for item in item_list:
		try:
			item_price = get_active_price(item, supplier)
		except:
			frappe.throw('Please check again, some items do not have a defined price for this supplier')
		if (item_price == None):
			frappe.throw('Please check again, some items do not have a defined price for this supplier')
		if item_price.depends_on_attribute:
			attribute_qty_sum = {}
			attribute_indexes = {}
			for index, i in enumerate(items):
				d = frappe.get_doc("Item Variant", i['item_variant'])
				if d.item == item:
					for attribute in d.attributes:
						if attribute.attribute == item_price.attribute:
							if attribute_indexes.get(attribute.attribute_value):
								attribute_indexes[attribute.attribute_value].append(index)
								attribute_qty_sum[attribute.attribute_value] += i['qty']
							else:
								attribute_indexes[attribute.attribute_value] = [index]
								attribute_qty_sum[attribute.attribute_value] = i['qty']
							break
			for attr, value in attribute_indexes.items():
				qty_sum = attribute_qty_sum[attr]
				price = item_price.validate_attribute_values(qty=qty_sum, attribute=item_price.attribute, attribute_value=attr)
				if price == None:
					frappe.throw('Please check again, some items do not have a defined price for this supplier')
				for index in value:
					items[index]['rate'] = price
					items[index]['tax'] = item_price.tax
		else:
			qty_sum = 0
			indexes = []
			for index, i in enumerate(items):
				d = frappe.db.get_value("Item Variant", i['item_variant'], 'item')
				if d == item:
					qty_sum += i['qty']
					indexes.append(index)
			price = item_price.validate_attribute_values(qty=qty_sum)
			if price == None:
				frappe.throw('Please check again, some items do not have a defined price for this supplier')
			for index in indexes:
				items[index]['rate'] = price
				items[index]['tax'] = item_price.tax
	return items

def get_unique_items(items):
	unique_items = []
	for item in items:
		iv = item['item_variant']
		i = frappe.db.get_value('Item Variant', iv, 'item')
		if not i in unique_items:
			unique_items.append(i)
	return unique_items


def save_item_details(item_details):
	"""
		Save item details to purchase order
		Item details format:
		Eg: see sample_po_item.jsonc
	"""
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
					if values.get('qty'):
						item_attributes[item.get('primary_attribute')] = attr
						item1 = {}
						variant_name = get_variant(item_name, item_attributes)
						if not variant_name:
							variant1 = create_variant(item_name, item_attributes)
							variant1.insert()
							variant_name = variant1.name
						item1['item_variant'] = variant_name
						item1['delivery_location'] = item['delivery_location']
						item1['delivery_date'] = item['delivery_date']
						item1['lot'] = item.get('lot')
						item1['qty'] = values.get('qty')
						item1['uom'] = values.get('default_uom')
						item1['secondary_qty'] = values.get('secondary_qty')
						item1['secondary_uom'] = values.get('secondary_uom')
						item1['rate'] = values.get('rate')
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['comments'] = item.get('comments')
						items.append(item1)
			else:
				if item['values'].get('default') and item['values']['default'].get('qty'):
					print(item_name)
					item1 = {}
					variant_name = get_variant(item_name, item_attributes)
					if not variant_name:
						variant1 = create_variant(item_name, item_attributes)
						variant1.insert()
						variant_name = variant1.name
					item1['item_variant'] = variant_name
					item1['delivery_location'] = item['delivery_location']
					item1['delivery_date'] = item['delivery_date']
					item1['lot'] = item.get('lot')
					item1['qty'] = item['values']['default'].get('qty')
					item1['uom'] = item.get('default_uom')
					item1['secondary_qty'] = item['values']['default'].get('secondary_qty')
					item1['secondary_uom'] = item.get('secondary_uom')
					item1['rate'] = item['values']['default'].get('rate')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['comments'] = item.get('comments')
					items.append(item1)
			row_index += 1
	return items

def get_item_attribute_details(variant, item_attributes):
	attribute_details = {}
	
	for attr in variant.attributes:
		if attr.attribute in item_attributes['attributes']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

def get_item_group_index(items, item_details):
	index = -1
	for i, item in enumerate(items):
		item_attr = item.get('attributes')
		item_details_attr = item_details.get('attributes')
		item_attr.sort()
		item_details_attr.sort()
		if not (len(item_attr) == len(item_details_attr) and len(item_attr) == sum([1 for i, j in zip(item_attr, item_details_attr) if i == j])):
			continue
		if not item.get('primary_attribute') == item_details.get('primary_attribute'):
			continue
		if not item.get('primary_attribute_values').sort() == item_details.get('primary_attribute_values').sort():
			continue
		index = i
		break
	return index

@frappe.whitelist()
def fetch_item_details(items, include_id:bool=False):
	items = [item.as_dict() for item in items]
	item_details = []
	items = sorted(items, key = lambda i: i['row_index'])
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'lot': variants[0]['lot'],
			'delivery_location': variants[0]['delivery_location'],
			'delivery_date': str(variants[0]['delivery_date']),
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
							'qty': variant.qty,
							'secondary_qty': variant.secondary_qty,
							'pending_qty': variant.pending_qty,
							'rate': variant.rate,
							'tax': variant.tax,
						}
						if include_id:
							item['values'][attr.attribute_value]['ref_doctype'] = "Purchase Order Item"
							item['values'][attr.attribute_value]['ref_docname'] = variant.name
						break
		else:
			item['values']['default'] = {
				'qty': variants[0].qty,
				'secondary_qty': variants[0].secondary_qty,
				'pending_qty': variants[0].pending_qty,
				'rate': variants[0].rate,
				'tax': variants[0].tax
			}
			if include_id:
				item['values']['default']['ref_doctype'] = "Purchase Order Item"
				item['values']['default']['ref_docname'] = variants[0].name
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
def get_address_display(address_dict):
	if not address_dict:
		return

	if not isinstance(address_dict, dict):
		address_dict = frappe.db.get_value("Address", address_dict, "*", as_dict=True, cache=True) or {}

	# name, template = get_address_templates(address_dict)
	template = '''
		{{ address_line1 }}, {% if address_line2 %}{{ address_line2 }}{% endif -%}<br>
		{{ city }}, {% if state %}{{ state }}{% endif -%}{% if pincode %} - {{ pincode }}{% endif -%}
	'''

	try:
		return frappe.render_template(template, address_dict)
	except TemplateSyntaxError:
		frappe.throw(_("There is an error in your Address Template"))

def get_PO_print_details(docname):
	item_names = []
	item_quantities = {} # Group based on UOM
	po = frappe.get_doc("Purchase Order", docname)
	# for all item variants in the PO Get the Parent Item name
	for item in po.items:
		parent_item = frappe.db.get_value("Item Variant", item.item_variant, "item")
		if parent_item not in item_names:
			item_names.append(parent_item)
		# check if uom already exists in the dict
		if item.uom in item_quantities:
			item_quantities[item.uom] += item.qty
		else:
			item_quantities[item.uom] = item.qty
	item_qty_string = ""
	for uom, qty in item_quantities.items():
		item_qty_string += str(qty) + " " + uom + ", "
	if item_qty_string:
		item_qty_string = item_qty_string[:-2]
	total_with_currency = frappe.utils.fmt_money(po.grand_total, currency="Rs")
	return {
		"item_names": ', '.join(item_names),
		"item_quantities": item_qty_string,
		"amount": total_with_currency,
	}

@frappe.whitelist()
def get_purchase_order_items(purchase_order):
	po = frappe.get_doc("Purchase Order", purchase_order)
	return fetch_item_details(po.items, include_id=True)

@frappe.whitelist()
def cancel_purchase_order(purchase_order, reason=None):
	po = frappe.get_doc("Purchase Order", purchase_order)
	draft_grns = frappe.get_all("Goods Received Note", filters={
		"against": "Purchase Order",
		"against_id": purchase_order,
		"docstatus": 0,
	})
	if draft_grns:
		frappe.throw(_("Cannot cancel Purchase Order as there are Goods Received Notes in draft state"))
	
	pending_items = [item.pending_qty==item.qty for item in po.items]
	print("pending_items", pending_items)
	if all(pending_items):
		po.set("cancel_reason", reason)
		po.save()
		po.cancel()
		return
	delivered_items = [item.pending_qty==0 for item in po.items]
	print("delivered_items", delivered_items)
	if all(delivered_items):
		frappe.throw(_("Cannot cancel Purchase Order as all items are delivered"))
	for item in po.items:
		item.cancelled_qty = item.qty
		item.pending_qty = 0
	po.set("cancel_reason", reason)
	po.save()
	
@frappe.whitelist()
def refresh_status(purchase_order):
	po = frappe.get_doc("Purchase Order", purchase_order)
	status = po.status
	po.set_status()
	if status != po.status:
		po.save()
	return po.status