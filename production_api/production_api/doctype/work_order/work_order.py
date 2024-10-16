# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe,json
from six import string_types
from frappe.utils import flt
from frappe import _
from itertools import groupby
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import get_variant, create_variant, get_attribute_details, get_or_create_variant
from production_api.essdee_production.doctype.lot.lot import fetch_order_item_details 
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_calculated_bom
from production_api.essdee_production.doctype.lot.lot import get_uom_conversion_factor
import math

class WorkOrder(Document):
	def on_update_after_submit(self):
		check_quantity = True
		for item in self.deliverables:
			if float(item.pending_quantity) > float(0):
				check_quantity = False
				break

		if check_quantity and self.deliverables:
			self.set('is_delivered',1)

	def onload(self):
		deliverable_item_details = fetch_item_details(self.get('deliverables'))
		self.set_onload('deliverable_item_details', deliverable_item_details)

		receivable_item_details = fetch_item_details(self.get('receivables'))
		self.set_onload('receivable_item_details', receivable_item_details)

	def before_save(self):
		if self.docstatus == 1:
			return
		for item in self.deliverables:
			item.set('pending_quantity', item.qty)
			item.set('cancelled_quantity', 0)

		for item in self.receivables:
			item.set('pending_quantity', item.qty)

	def before_validate(self):
		if self.docstatus == 1:
			return
		if(self.get('deliverable_item_details')):
			items = save_item_details(self.deliverable_item_details)
			self.set("deliverables",items)

		if(self.get('receivable_item_details')):
			items = save_item_details(self.receivable_item_details,process_name=self.process_name,wo_date=self.wo_date,ipd=self.production_detail)
			self.set("receivables",items)

def save_item_details(item_details, process_name = None, wo_date = None, ipd = None):
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
						item1 = get_data(item,item_name,item_attributes,table_index,row_index, process_name, quantity, wo_date, ipd)	
						item1['secondary_qty'] = values.get('secondary_qty')
						item1['secondary_uom'] = values.get('secondary_uom')
						items.append(item1)
			else:
				if item['values'].get('default') and item['values']['default'].get('qty'):
					quantity = item['values']['default'].get('qty')
					item1 = get_data(item,item_name,item_attributes,table_index,row_index, process_name, quantity, wo_date)	
					item1['secondary_qty'] = item['values']['default'].get('secondary_qty')
					item1['secondary_uom'] = item.get('secondary_uom')
					items.append(item1)
			row_index += 1
	return items

def get_data(item, item_name, item_attributes, table_index, row_index, process_name, quantity, wo_date, ipd):
	item1 = {}
	variant_name = get_variant(item_name, item_attributes)
	if not variant_name:
		variant1 = create_variant(item_name, item_attributes)
		variant1.insert()
		variant_name = variant1.name
	if process_name:
		rate, cost_doc = get_rate_and_quantity(process_name,variant_name,quantity,wo_date)
		attr_qty = get_attributes_qty(ipd,process_name,cost_doc)
		rate = rate / attr_qty
		total_cost = flt(rate) * flt(quantity)
		item1['cost'] = rate
		item1['total_cost'] = total_cost		
	item1['qty'] = quantity
	item1['item_variant'] = variant_name
	item1['lot'] = item.get('lot')
	item1['uom'] = item.get('default_uom')
	item1['table_index'] = table_index
	item1['row_index'] = row_index
	item1['comments'] = item.get('comments') 

	return item1	

def get_rate_and_quantity(process_name, variant_name, quantity, wo_date):
	item_doc = frappe.get_doc('Item Variant',variant_name)
	item = item_doc.item
	doc_names = frappe.get_list('Process Cost',filters = {
		'process_name':process_name,
		'item':item,
		'is_expired':0,
		'from_date':['<=',wo_date],
		'to_date':['>=',wo_date],
		'docstatus': 1,
	})
	docname = None
	if doc_names:
		docname = doc_names[0]['name']
	
	if not docname:
		frappe.throw('No process cost for ' + item)
	
	rate = 0
	order_quantity = 0
	low_price = 0
	found = False

	doc = frappe.get_doc('Process Cost', docname)
	if doc.depends_on_attribute:
		attribute = doc.attribute
		attribute_value = next((attr.attribute_value for attr in item_doc.attributes if attr.attribute == attribute), None)
		for cost_values in doc.process_cost_values:
			cost = cost_values.as_dict()
			if cost['min_order_qty'] > quantity and cost['attribute_value'] == attribute_value:
				rate = cost['price']
				found = True
				break
			if order_quantity <= cost['min_order_qty'] and cost['attribute_value'] == attribute_value:
				order_quantity = cost['min_order_qty']
				low_price = cost['price']
	else:
		
		for cost_values in doc.process_cost_values:
			cost = cost_values.as_dict()
			if cost['min_order_qty'] > quantity:
				rate = cost['price']
				found = True
				break
			if order_quantity <= cost['min_order_qty']:
				order_quantity = cost['min_order_qty']
				low_price = cost['price']		
	if not found:
		return low_price,docname

	return rate,docname	

import copy
def fetch_item_details(items, include_id = False):
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
		if variants[0].cost:
			item['cost'] = variants[0].cost
		if variants[0].total_cost:
			item['total_cost'] = variants[0].total_cost	

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
							'cost':variant.cost,
						}
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
				'cost': variants[0].cost,
			}
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
def check_process(process, ipd):
	ipd_doc = frappe.get_doc("Item Production Detail",ipd)
	process_exist = False
	if ipd_doc.stiching_process == process:
		process_exist = True
	elif ipd_doc.packing_process == process:
		process_exist = True
	elif ipd_doc.cutting_process == process:
		process_exist = True
	else:		
		for item in ipd_doc.ipd_processes:
			if item.process_name == process:
				process_exist = True
				break
	if process_exist:
		return True
	return None		

@frappe.whitelist()
def get_work_order_items(work_order):
	wo = frappe.get_doc("Work Order", work_order)
	data = fetch_item_details(wo.receivables, include_id=True)
	return data
 
@frappe.whitelist()
def get_lot_items(lot, process):
	doc = frappe.get_doc("Lot", lot)	
	items = fetch_order_item_details(doc.lot_order_details, doc.production_detail)
	return items

@frappe.whitelist()
def get_deliverable_receivable( lot, process, items, doc_name):
	lot_doc = frappe.get_doc("Lot", lot)
	ipd = lot_doc.production_detail
	uom = lot_doc.packing_uom
	pack_out_uom = lot_doc.uom

	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	dept_attribute = ipd_doc.dependent_attribute
	pack_out_stage = ipd_doc.pack_out_stage
	stiching_in_stage = ipd_doc.stiching_in_stage

	items = get_items(items)
	grp_variant = items[0]['item_variant']
	item_name = frappe.get_value("Item Variant", grp_variant, 'item')
	item_list, row_index, table_index = get_item_structure(items, item_name, process, uom)

	bom = get_calculated_bom(ipd, items, lot, process, from_uom=uom, to_uom=uom)
	print(bom)
	bom = get_bom_structure(bom, row_index, table_index)

	deliverables = []
	receivables = []
	doc = frappe.get_doc("Work Order", doc_name)

	if ipd_doc.stiching_process == process:
		receivables = get_receivables(item_list, process, lot, uom, doc.wo_date, ipd)
		stiching_attributes = get_attributes(item_list, item_name, stiching_in_stage, dept_attribute, ipd)
		stiching_attributes.update(bom)
		deliverables = get_deliverables(stiching_attributes, lot)
	
	elif ipd_doc.packing_process == process:
		packing_attributes = get_attributes(item_list, item_name, pack_out_stage, dept_attribute)
		item_list.update(bom)
		deliverables = get_deliverables(item_list, lot)
		item_doc = frappe.get_doc("Item", item_name)
		receivables = get_receivables(packing_attributes, process,lot, uom, doc.wo_date, ipd, conversion_details=item_doc.uom_conversion_details, out_uom=pack_out_uom)
		
	elif ipd_doc.cutting_process == process:
		cutting_out_stage = frappe.get_value("Item Production Detail", ipd,'cutting_out_stage')
		cutting_attributes = get_attributes(item_list, item_name, cutting_out_stage, dept_attribute,ipd)
		receivables = get_receivables(cutting_attributes, process, lot, uom, doc.wo_date, ipd)
		deliverables =  get_deliverables(bom, lot)
	
	else:		
		for item in ipd_doc.ipd_processes:
			if item.process_name == process:
				if ipd_doc.stiching_in_stage == item.stage:
					attributes = get_attributes(item_list, item_name, item.stage, dept_attribute, ipd)
					deliverables = get_deliverables(attributes, lot)
					receivables = deliverables	
				elif lot_doc.pack_in_stage == item.stage:
					deliverables = item_list.copy()
					receivables = get_receivables(deliverables, process, lot, uom, doc.wo_date, ipd)
					item_list.update(bom)
					deliverables = get_deliverables(item_list, lot)
				else:
					attributes = get_attributes(item_list, item_name, item.stage, dept_attribute)
					receivables = get_receivables(attributes, process, lot, uom, doc.wo_date, ipd)
					attributes.update(bom)
					deliverables = get_deliverables(attributes, lot)
				break
	
	doc.set('deliverables',deliverables)
	doc.set('receivables', receivables)
	doc.save()

def get_deliverables(items, lot):
	deliverables = []
	for item_name,variants in items.items():
		for variant, details in variants.items():
			deliverables.append({
				'item_variant': variant,
				'lot':lot,
				'qty':details['qty'],
				'uom':details['uom'],
				'table_index': details['table_index'],
				'row_index':str(details['table_index'])+""+str(details['row_index']),
				'pending_quantity':details['qty'],
			})
	return deliverables

def get_receivables(items, process,lot, uom, wo_date, ipd, conversion_details = None, out_uom = None):
	receivables = []
	for item_name,variants in items.items():
		for variant, details in variants.items():
			rate, cost_doc = get_rate_and_quantity(process,variant,details['qty'],wo_date)
			print(rate)
			print(cost_doc)
			attr_qty = get_attributes_qty(ipd, process, cost_doc)
			rate = rate/attr_qty
			uom_factor = 1
			receivable_uom = uom
			if conversion_details:
				uom_factor = get_uom_conversion_factor(conversion_details, uom, out_uom)
				receivable_uom = out_uom
			qty = math.ceil(details['qty']*uom_factor)	
			receivables.append({
				'item_variant': variant,
				'lot':lot,
				'qty': qty,
				'cost': rate,
				'uom':receivable_uom,
				'table_index': details['table_index'],
				'row_index':details['row_index'],
				'pending_quantity':qty,
				'total_cost':rate*details['qty'],
			})
	return receivables	

def get_attributes_qty(ipd, process, process_cost_doc):
	doc = frappe.get_doc("Process Cost", process_cost_doc)
	if doc.depends_on_attribute:
		return 1
	ipd_doc = frappe.get_doc("Item Production Detail",ipd)
	if ipd_doc.cutting_process == process:
		return len(ipd_doc.stiching_item_details)
	return 1

def get_attributes(items, itemname, stage, dependent_attribute, ipd=None):
	item_list = {
		itemname: {}
	}
	ipd_doc = None
	if ipd:
		ipd_doc = frappe.get_doc("Item Production Detail", ipd)

	for item_name,variants in items.items():
		for variant, details in variants.items():
			current_variant = frappe.get_doc("Item Variant", variant)
			item_attribute_details = get_attribute_details(current_variant.item)
			attributes = get_receivable_item_attribute_details(current_variant, item_attribute_details, stage)

			if item_attribute_details['dependent_attribute']:
				attributes[dependent_attribute] = stage

			if not ipd_doc:
				new_variant = get_or_create_variant(itemname, attributes)
				if not item_list[itemname].get(new_variant, False):
					item_list[itemname][new_variant] = {
						'qty': details['qty'],
						'process': details['process'],
						'uom':details['uom'],
						'table_index':details['table_index'],
						'row_index':0
					}
				else:
					item_list[itemname][new_variant]['qty'] += details['qty']	
			else:
				for id,item in enumerate(ipd_doc.stiching_item_details):
					attributes[ipd_doc.stiching_attribute] = item.stiching_attribute_value
					new_variant = get_or_create_variant(itemname, attributes)
					item_list[itemname][new_variant] = {
						'qty': details['qty']*item.quantity,
						'process': details['process'],
						'uom':details['uom'],
						'table_index':details['table_index'],
						'row_index':str(details['table_index'])+""+str(details['row_index'])+""+str(id)
					}
	return item_list

def get_receivable_item_attribute_details(variant, item_attributes, stage):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute in item_attributes['dependent_attribute_details']['attr_list'][stage]['attributes']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

def get_items(items):
	if isinstance(items, string_types):
		items = json.loads(items)
	if len(items[0]['items']) == 0:
		return []
	item = items[0]
	item_list = []
	for id1, row in enumerate(item['items']):
		if row['primary_attribute']:
			attributes = row['attributes']
			attributes[item['dependent_attribute']] = item['final_state']	
			for id2, val in enumerate(row['work_order_qty'].keys()):
				attributes[row['primary_attribute']] = val
				item1 = {}
				variant_name = get_variant(item['item'], attributes)
				if not variant_name:
					variant1 = create_variant(item['item'], attributes)
					variant1.insert()
					variant_name = variant1.name
				item1['item_variant'] = variant_name
				item1['qty'] = row['work_order_qty'][val]
				item1['row_index'] = id1
				item1['table_index'] = id1
				if item1['qty']:
					item_list.append(item1)
		else:
			item1 = {}
			attributes = row['attributes']
			variant_name = item['item']
			variant_name = get_variant(item['item'], attributes)
			if not variant_name:
				variant1 = create_variant(item['item'], attributes)
				variant1.insert()
				variant_name = variant1.name
			item1['item_variant'] = variant_name
			item1['qty'] = row['work_order_qty']
			item1['table_index'] = id1
			item1['row_index'] = id1
			if item1['qty']:
				item_list.append(item1)
	return item_list

def get_item_structure(items,item_name, process, uom):
	item_list = {
		item_name: {}
	}
	row_index = 0
	table_index = 0
	for item in items:
		row_index = item['row_index']
		table_index = item['table_index']
		item_list[item_name][item['item_variant']] = {
			"qty":item['qty'],
			"process":process,
			"uom":uom,
			"row_index":row_index,
			"table_index":table_index
		}
	return item_list, row_index, table_index	

def get_bom_structure(items, row_index, table_index):
	for item_name,values in items.items():
		table_index = table_index + 1
		for item,value in values.items():
			row_index = row_index + 1
			items[item_name][item] = {
				"qty":value[0],
				"process":value[1],
				"uom":value[2],
				"row_index":row_index,
				"table_index":table_index
			}
	return items
	