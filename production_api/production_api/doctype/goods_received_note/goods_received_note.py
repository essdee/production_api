# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

from itertools import groupby
import frappe
from frappe import _
from frappe.utils import money_in_words
from frappe.model.document import Document
from six import string_types
import json

from production_api.production_api.doctype.item.item import get_variant, create_variant, get_attribute_details
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index

class GoodsReceivedNote(Document):
	def onload(self):
		print('in onload')
		item_details = fetch_grn_item_details(self.get('items'), docstatus=self.docstatus)
		self.set('print_item_details', json.dumps(item_details))
		self.set_onload('item_details', item_details)
	
	def before_save(self):
		self.calculate_amount()

	def before_submit(self):
		against_docstatus = frappe.get_value(self.against, self.against_id, 'docstatus')
		if against_docstatus != 1:
			frappe.throw(f'{self.against} is not submitted.', title='GRN')
		# Remove all item rows quantity is zero
		for item in self.items:
			if item.quantity == 0:
				self.items.remove(item)
		self.validate_quantity()
		self.calculate_amount()
		self.set('approved_by', frappe.get_user().doc.name)
	
	def on_submit(self):
		self.update_purchase_order()
	
	def on_cancel(self):
		settings = frappe.get_single('MRP Settings')
		cancel_before_days = settings.grn_cancellation_in_days
		if cancel_before_days == 0:
			frappe.throw('GRN cancellation is not allowed.', title='GRN')
		if cancel_before_days and not settings.allow_grn_cancellation:
			if (frappe.utils.nowdate() - self.creation).days > cancel_before_days:
				frappe.throw(f'GRN cannot be cancelled after {cancel_before_days} days of creation.', title='GRN')
		if self.against == 'Purchase Order':
			status = frappe.get_value('Purchase Order', self.against_id, 'open_status')
			if status != 'Open':
				frappe.throw('Purchase order is not open.', title='GRN')
		self.update_purchase_order()

	def update_purchase_order(self):
		if self.docstatus == 0:
			return
		multiplier = 1
		if self.docstatus == 2:
			multiplier = -1
		po = frappe.get_doc(self.against, self.against_id)
		for item in self.items:
			# find the po item with the same ref_docname
			for i in po.items:
				if i.name == item.ref_docname:
					quantity = item.quantity * multiplier
					if self.docstatus == 1:
						validate_quantity_tolerance(i.item_variant, i.qty, i.pending_qty, quantity)
					i.set('pending_qty', i.pending_qty - quantity)
					break
		po.save(ignore_permissions=True)


	def before_validate(self):
		if(self.get('item_details')):
			items = save_grn_item_details(self.item_details)
			print(json.dumps(items, indent=3))
			self.set('items', items)
		elif self.is_new() or not self.get('items'):
			frappe.throw('Add items to GRN.', title='GRN')
	
	def validate(self):
		if self.against == 'Purchase Order':
			status = frappe.get_value('Purchase Order', self.against_id, 'open_status')
			if status != 'Open':
				frappe.throw('Purchase order is not open.', title='GRN')
			supplier = frappe.get_value('Purchase Order', self.against_id, 'supplier')
			if supplier != self.supplier:
				frappe.throw('Supplier cannot be changed.', title='GRN')
			po_docstatus = frappe.get_value('Purchase Order', self.against_id, 'docstatus')
			if po_docstatus != 1:
				frappe.throw('Purchase order is not submitted.', title='GRN')
		
		self.validate_quantity()
	
	def validate_quantity(self):
		total_quantity = 0
		for item in self.items:
			total_quantity += item.quantity
		if total_quantity == 0:
			frappe.throw('Quantity cannot be zero.', title='GRN')
	
	def calculate_amount(self):
		total_amount = 0
		total_tax = 0
		grand_total = 0
		for item in self.items:
			item_total = item.rate * item.quantity
			total_amount += item_total
			tax = item_total * (float(item.tax or 0) / 100)
			total_tax += tax
			total = item_total + tax
			grand_total += total
		self.set('total', total_amount)
		self.set('total_tax', total_tax)
		self.set('grand_total', grand_total)
		self.set('in_words', money_in_words(grand_total))

def save_grn_item_details(item_details):
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
					if values.get('qty') or values.get('pending_qty') or values.get('received'):
						item_attributes[item.get('primary_attribute')] = attr
						item1 = {}
						variant_name = get_variant(item_name, item_attributes)
						if not variant_name:
							variant1 = create_variant(item_name, item_attributes)
							variant1.insert()
							variant_name = variant1.name
						validate_quantity_tolerance(variant_name, values.get('qty'), values.get('pending_qty'), values.get('received'))
						item1['item_variant'] = variant_name
						item1['lot'] = item.get('lot')
						# Convert to number if string
						if isinstance(values.get('received'), string_types) and values.get('received') != '':
							values['received'] = float(values.get('received'))
						else:
							values['received'] = values.get('received') or 0
						item1['quantity'] = values.get('received')
						item1['uom'] = item.get('default_uom')
						if isinstance(values.get('secondary_received'), string_types) and values.get('secondary_received') != '':
							values['secondary_received'] = float(values.get('secondary_received'))
						else:
							values['secondary_received'] = values.get('secondary_received') or 0
						item1['secondary_qty'] = values.get('secondary_received')
						item1['secondary_uom'] = item.get('secondary_uom')
						item1['rate'] = values.get('rate')
						item1['tax'] = values.get('tax')
						item1['table_index'] = table_index
						item1['row_index'] = row_index
						item1['comments'] = item.get('comments')
						item1['ref_doctype'] = values.get('ref_doctype')
						item1['ref_docname'] = values.get('ref_docname')
						items.append(item1)
			else:
				if item['values'].get('default'):
					print(item_name)
					item1 = {}
					variant_name = get_variant(item_name, item_attributes)
					if not variant_name:
						variant1 = create_variant(item_name, item_attributes)
						variant1.insert()
						variant_name = variant1.name
					validate_quantity_tolerance(variant_name, item['values']['default'].get('qty'), item['values']['default'].get('pending_qty'), item['values']['default'].get('received'))
					item1['item_variant'] = variant_name
					item1['lot'] = item.get('lot')
					item1['quantity'] = item['values']['default'].get('received')
					item1['uom'] = item.get('default_uom')
					item1['secondary_qty'] = item['values']['default'].get('secondary_received')
					item1['secondary_uom'] = item.get('secondary_uom')
					item1['rate'] = item['values']['default'].get('rate')
					item1['tax'] = item['values']['default'].get('tax')
					item1['table_index'] = table_index
					item1['row_index'] = row_index
					item1['comments'] = item.get('comments')
					item1['ref_doctype'] = item['values']['default'].get('ref_doctype')
					item1['ref_docname'] = item['values']['default'].get('ref_docname')
					items.append(item1)
			row_index += 1
	return items

def validate_quantity_tolerance(item_variant, total_qty, pending_qty, received_qty):
	item = frappe.get_value("Item Variant", item_variant, "item")
	# tolerance percentage
	tolerance_percentage = frappe.get_value("Item", item, "over_delivery_receipt_allowance") or 0
	tolerance = total_qty * (tolerance_percentage / 100)
	# Check if the tolerance is exceeded
	if (received_qty - pending_qty) > tolerance:
		frappe.throw(_("Quantity tolerance exceeded for item {0}. Received Quantity must not exceed {1}").format(item, pending_qty + tolerance))
	return True

def fetch_grn_item_details(items, docstatus=0):
	items = [item.as_dict() for item in items]
	# Delete all rows where quantity is 0 if docstatus is not 0
	if docstatus != 0:
		items = [item for item in items if item.get('quantity') > 0]
	item_details = []
	items = sorted(items, key = lambda i: i['row_index'])
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
							'received': variant.quantity,
							'secondary_received': variant.secondary_qty,
							'rate': variant.rate,
							'tax': variant.tax,
						}
						if docstatus == 0:
							doc = frappe.get_doc("Purchase Order Item", variant.ref_docname)
							item['values'][attr.attribute_value]['qty'] = doc.qty
							item['values'][attr.attribute_value]['secondary_qty'] = doc.secondary_qty
							item['values'][attr.attribute_value]['pending_qty'] = doc.pending_qty
							item['values'][attr.attribute_value]['ref_doctype'] = variant.ref_doctype
							item['values'][attr.attribute_value]['ref_docname'] = variant.ref_docname
						break
		else:
			item['values']['default'] = {
				'received': variants[0].quantity,
				'secondary_received': variants[0].secondary_qty,
				'rate': variants[0].rate,
				'tax': variants[0].tax
			}
			if docstatus == 0:
				print("docstatus")
				print(variants[0])
				doc = frappe.get_doc("Purchase Order Item", variants[0].ref_docname)
				item['values']['default']['qty'] = doc.qty
				item['values']['default']['secondary_qty'] = doc.secondary_qty
				item['values']['default']['pending_qty'] = doc.pending_qty
				item['values']['default']['ref_doctype'] = variants[0].ref_doctype
				item['values']['default']['ref_docname'] = variants[0].ref_docname
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