# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe,json
from six import string_types
from frappe.utils import money_in_words,flt, nowdate
from frappe import _
from itertools import groupby
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_variant, create_variant, get_attribute_details


class WorkOrder(Document):
	def on_update_after_submit(self):
		check_quantity = True
		for item in self.deliverables:
			if item.pending_quantity > 0:
				check_quantity = False
				break

		if check_quantity and self.deliverables:
			self.set('is_delivered',1)

	def onload(self):
		deliverable_item_details = fetch_item_details(self.get('deliverables'))
		self.set_onload('deliverable_item_details', deliverable_item_details)

		receivable_item_details = fetch_item_details(self.get('receivables'),process_name = self.process_name)
		self.set_onload('receivable_item_details', receivable_item_details)

	def before_save(self):
		if self.docstatus == 1:
			return
		total_amount = 0.0
		total_tax_amount = 0.0
		for item in self.deliverables:
			item.set('pending_quantity', item.qty)
			item.set('cancelled_quantity', 0)
		for item in self.receivables:
			item.set('pending_quantity', item.qty)
			temp_total = item.total_cost
			temp_tax = item.tax if item.tax else 0.0
			total_amount += temp_total
			x = temp_total/100.0
			x = flt(x) * flt(temp_tax)
			total_tax_amount += x
		self.set('total', total_amount)
		self.set('tax_total', total_tax_amount)
		self.set('grand_total', total_tax_amount + total_amount)
		self.set('in_words', money_in_words(total_tax_amount + total_amount))

	def validate(self):
		if len(self.receivables) == 0:
			frappe.throw("There are no items received")
				
	def before_validate(self):
		if self.docstatus == 1:
			return

		if(self.get('deliverable_item_details')):
			items = save_item_details(self.deliverable_item_details)
			self.set("deliverables",items)

		if(self.get('receivable_item_details')):
			items = save_item_details(self.receivable_item_details,self.supplier, self.process_name,self.wo_date)
			self.set("receivables",items)

def save_item_details(item_details,supplier = None, process_name = None, wo_date = None):
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
						quantity = values.get('qty')
						item_attributes[item.get('primary_attribute')] = attr
						item1 = get_data(item,item_name,item_attributes,table_index,row_index, process_name, quantity, wo_date, supplier)	
						item1['secondary_qty'] = values.get('secondary_qty')
						item1['secondary_uom'] = values.get('secondary_uom')
						items.append(item1)
			else:
				if item['values'].get('default') and item['values']['default'].get('qty'):
					quantity = item['values']['default'].get('qty')
					item1 = get_data(item,item_name,item_attributes,table_index,row_index, process_name, quantity, wo_date,supplier)	
					item1['secondary_qty'] = item['values']['default'].get('secondary_qty')
					item1['secondary_uom'] = item.get('secondary_uom')
					items.append(item1)
			row_index += 1
	return items



def get_data(item, item_name, item_attributes, table_index, row_index, process_name, quantity, wo_date, supplier):
	item1 = {}
	variant_name = get_variant(item_name, item_attributes)
	if not variant_name:
		variant1 = create_variant(item_name, item_attributes)
		variant1.insert()
		variant_name = variant1.name	
	if process_name:
		rate, tax = get_rate_and_quantity(process_name,variant_name,quantity,wo_date,item, supplier)
		total_cost = flt(rate) * flt(quantity)
		item1['cost'] = rate
		item1['total_cost'] = total_cost
		item1['tax'] = tax		
	item1['qty'] = quantity
	item1['item_variant'] = variant_name
	item1['lot'] = item.get('lot')
	item1['uom'] = item.get('default_uom')
	item1['table_index'] = table_index
	item1['row_index'] = row_index
	item1['comments'] = item.get('comments') 

	return item1	

def get_rate_and_quantity(process_name,variant_name, quantity, wo_date, item, supplier):
	dep_attr = item['dependent_attribute']
	dep_attr_value = None
	if dep_attr:
		dep_attr_value = item['attributes'][dep_attr]

	item_doc = frappe.get_doc('Item Variant',variant_name)
	item = item_doc.item
	filters = {
		'process_name':process_name,
		'item':item,
		'is_expired':0,
		'from_date':['<=',wo_date],
		'to_date':['>=',wo_date],
		'docstatus': 1,
	}
	if supplier:
		filters['supplier'] = supplier
	if dep_attr_value:
		filters['dependent_attribute_values'] = dep_attr_value

	doc_names = frappe.get_list('Process Cost',filters = filters)
	docname = None
	if doc_names:
		docname = doc_names[0]['name']
	else:
		del filters['supplier']
		doc_names = frappe.get_list('Process Cost',filters = filters)
		if doc_names:
			docname = doc_names[0]['name']
	if not docname:
		frappe.throw('No process cost for ' + item)
	
	rate = 0
	low_price = 0
	found = False

	doc = frappe.get_doc('Process Cost', docname)
	tax = doc.tax_slab
	if doc.depends_on_attribute:
		attribute = doc.attribute
		attribute_value = next((attr.attribute_value for attr in item_doc.attributes if attr.attribute == attribute), None)
		for cost_values in doc.process_cost_values:
			cost = cost_values.as_dict()
			if cost['min_order_qty'] >= quantity and cost['attribute_value'] == attribute_value:
				rate = cost['price']
				found = True
				break
			elif cost['attribute_value'] == attribute_value:
				low_price = cost['price']
	else:
		for cost_values in doc.process_cost_values:
			cost = cost_values.as_dict()
			if cost['min_order_qty'] >= quantity:
				rate = cost['price']
				found = True
				break
			else:
				low_price = cost['price']			
	if not found:
		return low_price, tax
	
	return rate, tax

def fetch_item_details(items, process_name = None,include_id = False):
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
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			"dependent_attribute": current_item_attribute_details['dependent_attribute'],
			"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
			'values': {},
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'secondary_uom': variants[0]['secondary_uom'] or current_item_attribute_details['secondary_uom'],
			'comments': variants[0]['comments'],
			'additional_parameters': variants[0]['additional_parameters'],
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
							'pending_qty': variant.pending_quantity,
							'cancelled_qty': variant.cancelled_qty,
							'rate': variant.rate,
							'tax': variant.tax,
						}
						if process_name:
							item['values'][attr.attribute_value]['cost'] = variant.cost
							item['values'][attr.attribute_value]['total_cost'] = variant.total_cost
							item['values'][attr.attribute_value]['tax'] = variant.tax
							

						if include_id:
							item['values'][attr.attribute_value]['ref_doctype'] = "Work Order Receivables"
							item['values'][attr.attribute_value]['ref_docname'] = variant.name
						break	
				
		else:
			item['values']['default'] = {
				'qty': variants[0].qty,
				'secondary_qty': variants[0].secondary_qty,
				'pending_qty': variants[0].pending_quantity,
				'cancelled_qty': variants[0].cancelled_qty,
				'rate': variants[0].rate,
				'tax': variants[0].tax,
			}
			
			if process_name:
				item['values']['default']['cost'] = variants[0].cost
				item['values']['default']['total_cost'] = variants[0].total_cost
				item['values']['default']['tax'] = variants[0].tax
				


			if include_id:
				item['values']['default']['ref_doctype'] = "Work Order Receivables"
				item['values']['default']['ref_docname'] = variants[0].name
		index = get_item_group_index(item_details, current_item_attribute_details)

		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				"dependent_attribute": current_item_attribute_details['dependent_attribute'],
				"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
				'additional_parameters': current_item_attribute_details['additional_parameters'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	

	return item_details

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
		if not item.get('dependent_attribute') == item_details.get('dependent_attribute'):
			continue
		index = i
		break
	return index

def get_item_attribute_details(variant, item_attributes):
	attribute_details = {}
	
	for attr in variant.attributes:
		if attr.attribute in item_attributes['attributes']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

@frappe.whitelist()
def get_work_order_items(work_order):
	wo = frappe.get_doc("Work Order", work_order)
	data = fetch_item_details(wo.receivables,process_name = None, include_id=True)
	return data
@frappe.whitelist()
def check_delivered_and_received(doc_name):
	doc = frappe.get_doc('Work Order', doc_name)
	deliverable = doc.deliverables
	for data in deliverable:
		row = data.as_dict()
		if row.pending_quantity > 0:
			return False,"Deliverable"

	receivable = doc.receivables
	for data in receivable:
		row = data.as_dict()
		if row.pending_quantity > 0:
			return False,"Receivable"	

	doc.end_date = nowdate()
	doc.update()

@frappe.whitelist()
def add_comment(doc_name, date, reason):
	doc = frappe.get_doc('Work Order', doc_name)
	doc.expected_delivery_date = date
	text = f"Delivery date changed to {date} due to {reason}"
	doc.add_comment('Comment',text=text)
	doc.save()




