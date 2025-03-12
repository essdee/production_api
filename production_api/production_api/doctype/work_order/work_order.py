# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

from frappe import _
import frappe, json, math
from six import string_types
from itertools import groupby
from datetime import datetime
from frappe.model.document import Document
from frappe.utils import flt, nowdate, nowtime
from production_api.mrp_stock.stock_ledger import make_sl_entries
from production_api.production_api.logger import get_module_logger
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_group_index
from production_api.production_api.doctype.item.item import get_attribute_details, get_or_create_variant
from production_api.production_api.doctype.delivery_challan.delivery_challan import get_variant_stock_details
from production_api.essdee_production.doctype.lot.lot import fetch_order_item_details, get_uom_conversion_factor
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_calculated_bom, get_or_create_ipd_variant

class WorkOrder(Document):
	def on_update_after_submit(self):
		check_quantity = True
		for item in self.deliverables:
			if flt(item.pending_quantity) > flt(0):
				check_quantity = False
				break

		if check_quantity and self.deliverables:
			self.set('is_delivered',1)

	def onload(self):
		deliverable_item_details = fetch_item_details(self.get('deliverables'),self.production_detail, process=self.process_name,is_calc=True)
		self.set_onload('deliverable_item_details', deliverable_item_details)

		receivable_item_details = fetch_item_details(self.get('receivables'),self.production_detail, process=self.process_name)
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
		frappe.flags.check = True
		calculate = True
		if not self.is_new():
			process = frappe.db.get_value("Work Order",self.name,"process_name")
			if process != self.process_name:
				calculate = False
		if calculate:		
			if(self.get('deliverable_item_details')):
				items = save_item_details(self.deliverable_item_details, self.production_detail)
				self.set("deliverables",items)

			if(self.get('receivable_item_details')):
				frappe.flags.check = False
				items = save_item_details(self.receivable_item_details, self.production_detail, supplier=self.supplier, process_name=self.process_name)
				self.set("receivables",items)

			if frappe.flags.check and len(self.receivables) > 0:
				self.calc_receivable_rate()
		else:
			self.set("deliverables",[])
			self.set("receivables",[])	
			self.set("work_order_calculated_items",[])

	def calc_receivable_rate(self):		
		is_group = frappe.get_value("Process", self.process_name,"is_group")
		check = False
		if is_group:
			first_process = None
			final_process = None
			process_doc = frappe.get_cached_doc("Process",self.process_name)
			idx = -1
			for p in process_doc.process_details:
				idx += 1
				if idx == 0:
					first_process = p.process_name
				else:
					final_process = p.process_name
			ipd_doc = frappe.db.sql(
				f"""
					Select packing_process, stiching_process, cutting_process from `tabItem Production Detail`
					Where name = '{self.production_detail}'
				""", as_dict=True
			)[0]
			main_prs = [ipd_doc.packing_process, ipd_doc.stiching_process, ipd_doc.cutting_process]
			if first_process not in main_prs and final_process not in main_prs:	
				check = True				
		
		fil = {
			'process_name':self.process_name,
			'item':self.item,
			'is_expired':0,
			'from_date':['<=',self.wo_date],
			'docstatus': 1,
			"workflow_state":"Approved",
		}
		if self.is_rework:
			fil['is_rework'] = 1
		else:
			fil['is_rework'] = 0

		if self.supplier:
			fil['supplier'] = self.supplier

		doc_names = frappe.get_list('Process Cost',filters = fil)
		docname = None
		if doc_names:
			docname = doc_names[0]['name']
		else:
			del fil['supplier']
			docnames = frappe.get_list('Process Cost',filters = fil)
			if docnames:
				docname = docnames[0]['name']
		if not docname:
			frappe.throw('No process cost for ' + self.process_name)

		process_doc = frappe.get_doc("Process Cost", docname)
		ipd_doc = frappe.get_cached_doc("Item Production Detail", self.production_detail)
		stich_details = {}
		if ipd_doc.cutting_process == self.process_name:
			for item in ipd_doc.stiching_item_details:
				stich_details[item.stiching_attribute_value] = item.quantity

		for row in self.receivables:
			rate, attributes = get_rate_and_quantity(row.item_variant, row.qty, self, process_doc)
			attr_qty = get_attributes_qty(ipd_doc, self.process_name, process_doc.depends_on_attribute)
			if check:
				rate = rate / 2
			rate = rate/attr_qty
			if stich_details:
				rate = rate/stich_details[attributes.get(ipd_doc.stiching_attribute)]
			row.cost = round(rate,2)
			row.total_cost = round((rate * row.qty), 2)

def save_item_details(item_details, ipd, supplier=None, process_name = None):
	item_details = update_if_string_instance(item_details)
	ipd_doc = frappe.get_cached_doc("Item Production Detail",ipd)
	item_variants = update_if_string_instance(ipd_doc.variants_json)
	items = []
	row_index = 0
	table_index = -1
	for group in item_details:
		table_index += 1
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				for attr, values in item['values'].items():
					quantity = values.get('qty')
					if not quantity:
						quantity = 0
					item_attributes[item.get('primary_attribute')] = attr
					cost = values.get('cost')
					tup = tuple(sorted(item_attributes.items()))
					variant = get_or_create_ipd_variant(item_variants, item_name, tup, item_attributes)
					str_tup = str(tup)
					if item_variants and item_variants.get(item_name):
						if not item_variants[item_name].get(str_tup):
							item_variants[item_name][str_tup] = variant	
					else:	
						if not item_variants:
							item_variants = {}
							item_variants[item_name] = {}
							item_variants[item_name][str_tup] = variant
						else:
							item_variants[item_name] = {}
							item_variants[item_name][str_tup] = variant
					item1 = get_data(item, table_index, row_index, process_name, quantity, cost)
					item1['item_variant'] = variant	
					item1['set_combination'] = values.get("set_combination", {})
					item1['secondary_qty'] = values.get('secondary_qty')
					item1['secondary_uom'] = values.get('secondary_uom')
					if not supplier:
						item1['is_calculated'] = values.get('is_calculated') or 0
					items.append(item1)
			else:
				if item['values'].get('default') and item['values']['default'].get('qty'):
					quantity = item['values']['default'].get('qty')
					cost = item['values']['default'].get('cost')
					tup = tuple(sorted(item_attributes.items()))
					variant = get_or_create_ipd_variant(item_variants, item_name, tup, item_attributes)
					str_tup = str(tup)
					if item_variants and item_variants.get(item_name):
						if not item_variants[item_name].get(str_tup):
							item_variants[item_name][str_tup] = variant	
					else:	
						if not item_variants:
							item_variants = {}
							item_variants[item_name] = {}
							item_variants[item_name][str_tup] = variant
						else:
							item_variants[item_name] = {}
							item_variants[item_name][str_tup] = variant
					item1 = get_data(item,table_index,row_index, process_name, quantity,cost)	
					item1['item_variant'] = variant
					item1['set_combination'] = item['values']['default'].get('set_combination', {})
					item1['secondary_qty'] = item['values']['default'].get('secondary_qty')
					if not supplier:
						item1['is_calculated'] = item['values']['default'].get('is_calculated') or 0
					item1['secondary_uom'] = item.get('secondary_uom')
					items.append(item1)
			row_index += 1
	ipd_doc.db_set("variants_json", json.dumps(item_variants), update_modified=False)
	return items

def get_data(item, table_index, row_index, process_name, quantity, cost):
	item1 = {}
	if process_name:
		total_cost = flt(cost) * flt(quantity)
		item1['cost'] = round(cost,2)
		item1['total_cost'] = round(total_cost,2)		
	item1['qty'] = quantity
	item1['lot'] = item.get('lot')
	item1['uom'] = item.get('default_uom')
	item1['table_index'] = table_index
	item1['row_index'] = row_index
	item1['comments'] = item.get('comments') 
	return item1	

def get_rate_and_quantity(variant_name, quantity, doc, process_doc):
	item_doc = frappe.get_cached_doc('Item Variant',variant_name)
	rate = 0
	order_quantity = 0
	low_price = 0
	found = False

	attributes = {}
	for attr in item_doc.attributes:
		attributes[attr.attribute] = attr.attribute_value

	if doc.is_rework and doc.rework_type == 'No Cost':
		return flt(0) ,attributes
	
	if process_doc.depends_on_attribute:
		attribute = process_doc.attribute
		attribute_value = next((attr.attribute_value for attr in item_doc.attributes if attr.attribute == attribute), None)
		for cost_values in process_doc.process_cost_values:
			cost = cost_values.as_dict()
			if cost['min_order_qty'] > quantity and cost['attribute_value'] == attribute_value:
				rate = cost['price']
				found = True
				break
			if order_quantity <= cost['min_order_qty'] and cost['attribute_value'] == attribute_value:
				order_quantity = cost['min_order_qty']
				low_price = cost['price']
	else:
		for cost_values in process_doc.process_cost_values:
			cost = cost_values.as_dict()
			if cost['min_order_qty'] > quantity:
				rate = cost['price']
				found = True
				break
			if order_quantity <= cost['min_order_qty']:
				order_quantity = cost['min_order_qty']
				low_price = cost['price']		
	if not found:
		return round(low_price,2), attributes
	
	return round(rate,2), attributes

def fetch_item_details(items,ipd, process=None, include_id = False, is_grn= False, is_calc=False):
	items = [item.as_dict() for item in items]
	item_details = []
	items = sorted(items, key = lambda i: i['row_index'])
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)	

	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'lot': variants[0]['lot'],
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			"is_set_item": ipd_doc.is_set_item,
			"pack_attr":ipd_doc.packing_attribute,
			"set_attr":ipd_doc.set_item_attribute,
			"major_attr_value": ipd_doc.major_attribute_value,
			"item_keys":{},
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
			item['cost'] = round(variants[0].cost,2)
		if variants[0].total_cost:
			item['total_cost'] = round(variants[0].total_cost,2)	

		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				set_combination = update_if_string_instance(variant.set_combination)
				if set_combination:
					if set_combination.get("major_part"):
						item['item_keys']['major_part'] = set_combination.get("major_part")

					if set_combination.get("major_colour"):
						item['item_keys']['major_colour'] = set_combination.get("major_colour")		

				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'qty': variant.qty,
							'secondary_qty': variant.secondary_qty,
							'pending_qty': variant.pending_quantity,
							'cancelled_qty': variant.cancelled_qty,
							'rate': variant.rate,
							'tax': variant.tax,
							'cost': round(variant.cost, 2) if variant.cost else variant.cost,
							'set_combination':variant.set_combination,
						}
						if is_calc:
							item['values'][attr.attribute_value]['is_calculated'] = variant.is_calculated
						if is_grn:
							item['values'][attr.attribute_value]['qty'] = variant.pending_quantity
							item['values'][attr.attribute_value]['rate'] = round(variant.cost, 2) if variant.cost else variant.cost
							
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
				'cost': round(variants[0].cost, 2) if variants[0].cost else variants[0].cost,
				'set_combination': variants[0].set_combination,
			}
			if is_calc:
				item['values']['default']['is_calculated'] = variants[0].is_calculated
			if include_id:
				item['values']['default']['ref_doctype'] = "Work Order Receivables"
				item['values']['default']['ref_docname'] = variants[0].name
			if is_grn:
				item['values']['default']['qty'] = variants[0].pending_quantity
				item['values']['default']['rate'] = round(variants[0].cost, 2) if variants[0].cost else variants[0].cost

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

def get_item_attribute_details(variant, item_attributes):
	attribute_details = {}
	
	for attr in variant.attributes:
		if attr.attribute in item_attributes['attributes']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

@frappe.whitelist()
def get_work_order_items(work_order, is_grn = False):
	wo = frappe.get_doc("Work Order", work_order)
	data = fetch_item_details(wo.receivables,wo.production_detail,process = wo.process_name, include_id=True, is_grn= is_grn)
	return data
 
@frappe.whitelist()
def get_lot_items(lot, doc_name, process):
	logger = get_module_logger("work_order")
	logger.debug(f"{doc_name} Calculation Started {datetime.now()}")
	doc = frappe.get_cached_doc("Lot", lot)	
	items = fetch_order_item_details(doc.lot_order_details, doc.production_detail, process=process)
	logger.debug(f"{doc_name} Fetched Order detail from Lot {datetime.now()}")
	return items

@frappe.whitelist()
def get_deliverable_receivable( items, doc_name, deliverable=False, receivable=False):
	logger = get_module_logger("work_order")
	logger.debug(f"{doc_name} Deliverable and Receivable Calculation {datetime.now()}")
	wo_doc = frappe.get_cached_doc("Work Order", doc_name)
	lot_doc = frappe.db.sql(
		f"""
			Select production_detail, packing_uom, uom, pack_in_stage from `tabLot` where name = '{wo_doc.lot}'
		""", as_dict=True
	)[0]
	ipd = lot_doc.production_detail
	uom = lot_doc.packing_uom
	pack_out_uom = lot_doc.uom
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	dept_attribute = ipd_doc.dependent_attribute
	pack_out_stage = ipd_doc.pack_out_stage
	stiching_in_stage = ipd_doc.stiching_in_stage
	wo_colour_sets = get_report_data(items)
	items = get_items(items, ipd, deliverable=deliverable)
	grp_variant = items[0]['item_variant']
	item_name = frappe.get_value("Item Variant", grp_variant, 'item')
	item_list, row_index, table_index = get_item_structure(items, item_name, wo_doc.process_name, uom)
	deliverables = []
	receivables = []
	total_qty = 0
	is_group = frappe.get_value("Process",wo_doc.process_name,"is_group")
	if is_group:
		b = {}
		first_process = None
		final_process = None
		process_doc = frappe.get_cached_doc("Process",wo_doc.process_name)
		idx = -1
		for p in process_doc.process_details:
			idx += 1
			m = get_calculated_bom(ipd, items, wo_doc.lot, process_name=p.process_name, doctype="Work Order", deliverable=deliverable)
			b.update(m)
			if idx == 0:
				first_process = p.process_name
			else:
				final_process = p.process_name

		bom = get_bom_structure(b, row_index, table_index)	
		item_list2 = item_list.copy()
		deliverables , y,z= 	calc_deliverable_and_receivable(ipd_doc, first_process, item_list, item_name, dept_attribute, ipd, wo_doc.lot, uom, bom, lot_doc, stiching_in_stage, pack_out_stage, pack_out_uom)
		x, receivables, total_qty = calc_deliverable_and_receivable(ipd_doc, final_process, item_list2, item_name, dept_attribute, ipd, wo_doc.lot, uom, {}, lot_doc, stiching_in_stage, pack_out_stage, pack_out_uom)		
		main_prs = [ipd_doc.packing_process, ipd_doc.stiching_process, ipd_doc.cutting_process]
		if first_process not in main_prs and final_process not in main_prs:
			deliverables = deliverables + x
			receivables = receivables + y
			total_qty = total_qty + z
	else:
		bom = get_calculated_bom(ipd, items, wo_doc.lot, process_name=wo_doc.process_name,doctype="Work Order", deliverable=deliverable)
		bom = get_bom_structure(bom, row_index, table_index)
		deliverables, receivables, total_qty = calc_deliverable_and_receivable(ipd_doc, wo_doc.process_name, item_list, item_name, dept_attribute, ipd, wo_doc.lot, uom, bom, lot_doc, stiching_in_stage, pack_out_stage, pack_out_uom)		
	
	logger.debug(f"{doc_name} Calculation Completed {datetime.now()}")
	if deliverable:
		return deliverables
	if receivable:
		return receivables
	wo_doc.set('deliverables',deliverables)
	wo_doc.set('receivables', receivables)
	wo_doc.set("total_quantity", total_qty)
	wo_doc.set("work_order_calculated_items",items)
	wo_doc.set("wo_colours", wo_colour_sets)
	logger.debug(f"{doc_name} doc saved {datetime.now()}")
	wo_doc.save()
	processes = [ipd_doc.cutting_process]
	dc_processes = [ipd_doc.stiching_process]		

	for item in ipd_doc.ipd_processes:
		if item.process_name == wo_doc.process_name:
			if ipd_doc.stiching_in_stage == item.stage:
				processes.append(item.process_name)
				dc_processes.append(item.process_name)
				break


	if wo_doc.process_name in processes or wo_doc.process_name in dc_processes:
		from production_api.production_api.doctype.cutting_plan.cutting_plan import get_complete_incomplete_structure
		items = fetch_order_item_details(wo_doc.work_order_calculated_items, wo_doc.production_detail)
		complete, incomplete = get_complete_incomplete_structure(wo_doc.production_detail, items)
		if wo_doc.process_name in processes and wo_doc.process_name in dc_processes:
			wo_doc.set("completed_items_json", complete)
			wo_doc.set("incompleted_items_json",incomplete)
			wo_doc.set("wo_delivered_completed_json", complete)
			wo_doc.set("wo_delivered_incompleted_json",incomplete)
		else:
			if wo_doc.process_name in processes:
				wo_doc.set("completed_items_json", complete)
				wo_doc.set("incompleted_items_json",incomplete)
			else:
				wo_doc.set("wo_delivered_completed_json", complete)
				wo_doc.set("wo_delivered_incompleted_json",incomplete)
	else:
		wo_doc.set("completed_items_json", {})
		wo_doc.set("incompleted_items_json",{})
		wo_doc.set("wo_delivered_completed_json", {})
		wo_doc.set("wo_delivered_incompleted_json",{})
	wo_doc.save() 
	return None

def calc_deliverable_and_receivable(ipd_doc, process, item_list, item_name, dept_attribute, ipd, lot,uom, bom, lot_doc, stiching_in_stage, pack_out_stage, pack_out_uom):
	deliverables = []
	receivables = []
	total_qty = None
	if ipd_doc.stiching_process == process:
		receivables, total_qty  = get_receivables(item_list, lot, uom)
		stiching_attributes = get_attributes(item_list, item_name, stiching_in_stage, dept_attribute, ipd)
		stiching_attributes.update(bom)
		deliverables  = get_deliverables(stiching_attributes, lot)
	
	elif ipd_doc.packing_process == process:
		packing_attributes = get_attributes(item_list, item_name, pack_out_stage, dept_attribute, pack_ipd=ipd)
		item_list.update(bom)
		deliverables  = get_deliverables(item_list, lot)
		item_doc = frappe.get_cached_doc("Item", item_name)
		receivables, total_qty  = get_receivables(packing_attributes, lot, uom, conversion_details=item_doc.uom_conversion_details, out_uom=pack_out_uom)
		combine_dict = {}
		for item in receivables:
			combine_dict.setdefault(item['item_variant'], {
				"lot": item['lot'],
				"qty": 0,
				"uom": item['uom'],
				"table_index":item['table_index'],
				"row_index": item['row_index'],
				"pending_quantity": 0,
				"set_combination": {},
			})
			combine_dict[item['item_variant']]['qty'] += item['qty']
			combine_dict[item['item_variant']]['pending_quantity'] += item['qty']

		receivables = []
		for variant, details in combine_dict.items():
			x = {"item_variant": variant}
			x.update(details)
			receivables.append(x)	
		
	elif ipd_doc.cutting_process == process:
		cutting_out_stage = ipd_doc.stiching_in_stage
		cutting_attributes = get_attributes(item_list, item_name, cutting_out_stage, dept_attribute,ipd)
		receivables, total_qty  = get_receivables(cutting_attributes, lot, uom)
		deliverables  =  get_deliverables(bom, lot)

	else:	
		for item in ipd_doc.ipd_processes:
			if item.process_name == process:
				if ipd_doc.stiching_in_stage == item.stage:
					attributes = get_attributes(item_list, item_name, item.stage, dept_attribute, ipd, process)
					x = attributes.copy()
					x.update(bom)
					deliverables  = get_deliverables(x, lot)
					receivables, total_qty  = get_receivables(attributes, lot, uom)
				
				elif lot_doc.pack_in_stage == item.stage:
					deliverables = item_list.copy()
					receivables, total_qty  = get_receivables(deliverables,lot, uom)
					item_list.update(bom)
					deliverables = get_deliverables(item_list, lot)

				else:
					attributes = get_attributes(item_list, item_name, item.stage, dept_attribute, pack_ipd=ipd)
					receivables, total_qty = get_receivables(attributes,lot, uom)
					attributes.update(bom)
					deliverables = get_deliverables(attributes, lot)
				break
	return deliverables, receivables, total_qty

def get_deliverables(items, lot):
    deliverables = []
    for item_name, variants in items.items():
        for variant in variants:
            deliverables.append({
				'item_variant': variant['item_variant'],
				'lot':lot,
				'qty': round(variant['qty'],3),
				'uom':variant['uom'],
				'table_index': variant['table_index'],
				'row_index':str(variant['table_index'])+""+str(variant['row_index']),
				'pending_quantity':round(variant['qty'],3),
				'delivered_quantity':round(variant['qty'],3),
				'set_combination':variant.get('set_combination', {}),
				'is_calculated':True,
			})
    return deliverables

def get_report_data(items):
	attrs = []
	items = update_if_string_instance(items)
	wo_colour_sets = ""
	all_attrs = True	
	for item in items[0]['items']:
		check = False
		for val in item['work_order_qty']:
			if item['work_order_qty'][val] > 0:
				check = True
				break

		if check:
			attrs.append(item['attributes'])
		else:
			all_attrs = False	
	if all_attrs:
		wo_colour_sets = "All"
	else:	
		attributes = []
		for attr in attrs:
			attribute = "-".join(list(attr.values()))
			attributes.append(attribute)
		wo_colour_sets = ", ".join(attributes)	
	return wo_colour_sets

def get_receivables(items,lot, uom, conversion_details = None, out_uom = None):
	receivables = []
	total_qty = 0
	for item_name,variants in items.items():
		for variant in variants:
			uom_factor = 1
			receivable_uom = uom
			if conversion_details:
				uom_factor = get_uom_conversion_factor(conversion_details, uom, out_uom)
				receivable_uom = out_uom
			qty = math.ceil(variant['qty']*uom_factor)	
			total_qty += qty
			receivables.append({
				'item_variant': variant['item_variant'],
				'lot':lot,
				'qty': round(qty,3),
				'uom':receivable_uom,
				'table_index': variant['table_index'],
				'row_index':variant['row_index'],
				'pending_quantity':round(qty,3),
				'set_combination':variant['set_combination'],
			})
	return receivables, total_qty	

def get_attributes_qty(ipd_doc, process, depends_on_attr):
	if depends_on_attr:
		return 1
	
	emb = update_if_string_instance(ipd_doc.emblishment_details_json)
	if ipd_doc.stiching_process == process or ipd_doc.packing_process == process:
		return 1
	elif ipd_doc.cutting_process == process:
		if emb and emb.get(process):
			return len(emb.get(process))
		else:	
			return len(ipd_doc.stiching_item_details)
	else:
		for procesess in ipd_doc.ipd_processes:
			if procesess.process_name == process:
				if procesess.stage == ipd_doc.pack_in_stage or procesess.stage == ipd_doc.pack_out_stage:
					return 1
				elif procesess.stage == ipd_doc.stiching_in_stage:
					if emb and emb.get(process):
						return len(emb.get(process))
					else:	
						return len((ipd_doc.stiching_item_details))
	return 1

def get_attributes(items, itemname, stage, dependent_attribute, ipd=None, process=None, pack_ipd=None):
	item_list = {
		itemname: []
	}

	ipd_doc = None
	ipd_pack_doc = None
	item_variants = None
	part_list = []
	stiching_combination = None
	if ipd:
		from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_stitching_combination
		ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
		stiching_combination = get_stitching_combination(ipd_doc)
		item_variants = update_if_string_instance(ipd_doc.variants_json)

	if pack_ipd:
		ipd_pack_doc = frappe.get_cached_doc("Item Production Detail", pack_ipd)
		if ipd_pack_doc.is_set_item:
			for stich in ipd_pack_doc.stiching_item_details:
				if stich.set_item_attribute_value not in part_list:
					part_list.append(stich.set_item_attribute_value)

	for item_name, variants in items.items():
		item_attribute_details = get_attribute_details(item_name)
		for variant in variants:
			current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
			attributes = get_receivable_item_attribute_details(current_variant, item_attribute_details, stage)
			if item_attribute_details['dependent_attribute']:
				attributes[dependent_attribute] = stage
			itemname = current_variant.item
			if not ipd_doc:
				qty = variant['qty']
				if ipd_pack_doc.is_set_item:
					qty = qty / len(part_list)

				new_variant = get_or_create_variant(itemname, attributes)
				if not item_list.get(itemname):
					item_list[itemname] = []
					
				item_list[itemname].append({
					"item_variant":new_variant,
					'qty': qty,
					'process': variant['process'],
					'uom':variant['uom'],
					'table_index':variant['table_index'],
					'row_index':0,
					"set_combination":variant['set_combination']
				})
			else:
				set_item_stitching_attrs = {}
				if ipd_doc.is_set_item:
					part = None
					for attr in current_variant.attributes:
						if attr.attribute == ipd_doc.set_item_attribute:
							part = attr.attribute_value
							break

					for i in ipd_doc.stiching_item_details:
						set_item_stitching_attrs[i.stiching_attribute_value] = i.set_item_attribute_value
					id = -1
					for item in ipd_doc.stiching_item_details:
						id += 1
						if process:
							emb = update_if_string_instance(ipd_doc.emblishment_details_json)
							if emb.get(process):	
								if item.stiching_attribute_value in emb[process]:
									attributes[ipd_doc.stiching_attribute] = item.stiching_attribute_value
								else:
									continue		
							else:
								attributes[ipd_doc.stiching_attribute] = item.stiching_attribute_value			
						else:
							attributes[ipd_doc.stiching_attribute] = item.stiching_attribute_value
						v = True
						panel_part = set_item_stitching_attrs[item.stiching_attribute_value]
						if panel_part != part:
							v = False							
						if v:
							tup = tuple(sorted(attributes.items()))
							str_tup = str(tup)
							new_variant = get_or_create_ipd_variant(item_variants, itemname, tup, attributes)
							if item_variants and item_variants.get(itemname):
								if not item_variants[itemname].get(str_tup):
									item_variants[itemname][str_tup] = new_variant	
							else:	
								if not item_variants:
									item_variants = {}
									item_variants[itemname] = {}
									item_variants[itemname][str_tup] = new_variant
								else:
									item_variants[itemname] = {}
									item_variants[itemname][str_tup] = new_variant

							if not item_list.get(itemname):
								item_list[itemname] = []
							item_list[itemname].append({
								"item_variant":new_variant,
								'qty': variant['qty']*item.quantity,
								'process': variant['process'],
								'uom':variant['uom'],
								'table_index':variant['table_index'],
								'row_index':str(variant['table_index'])+""+str(variant['row_index'])+""+str(id),
								"set_combination":variant['set_combination']
							})
				else:
					id = -1
					for panel, colour in stiching_combination['stitching_combination'][attributes[ipd_doc.packing_attribute]].items():
						id += 1
						attributes[ipd_doc.packing_attribute] = colour
						if process:
							emb = update_if_string_instance(ipd_doc.emblishment_details_json)
							if emb.get(process):	
								if panel in emb[process]:
									attributes[ipd_doc.stiching_attribute] = panel
								else:
									continue		
							else:
								attributes[ipd_doc.stiching_attribute] = panel			
						else:
							attributes[ipd_doc.stiching_attribute] = panel
						
						tup = tuple(sorted(attributes.items()))
						str_tup = str(tup)
						new_variant = get_or_create_ipd_variant(item_variants, itemname, tup, attributes)
						if item_variants and item_variants.get(itemname):
							if not item_variants[itemname].get(str_tup):
								item_variants[itemname][str_tup] = new_variant	
						else:	
							if not item_variants:
								item_variants = {}
								item_variants[itemname] = {}
								item_variants[itemname][str_tup] = new_variant
							else:
								item_variants[itemname] = {}
								item_variants[itemname][str_tup] = new_variant

						if not item_list.get(itemname):
							item_list[itemname] = []
						item_list[itemname].append({
							"item_variant":new_variant,
							'qty': variant['qty'] * stiching_combination['stitching_attribute_count'][panel],
							'process': variant['process'],
							'uom':variant['uom'],
							'table_index':variant['table_index'],
							'row_index':str(variant['table_index'])+""+str(variant['row_index'])+""+str(id),
							"set_combination":variant['set_combination']
						})
	if ipd_doc:						
		ipd_doc.db_set("variants_json", json.dumps(item_variants), update_modified=False)
	return item_list

def get_receivable_item_attribute_details(variant, item_attributes, stage):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute in item_attributes['dependent_attribute_details']['attr_list'][stage]['attributes']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

def get_items(items, ipd, deliverable):
	items = update_if_string_instance(items)
	if len(items[0]['items']) == 0:
		return []
	ipd_doc = None
	item_variants = None
	if ipd:
		ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
		item_variants = update_if_string_instance(ipd_doc.variants_json)
	item = items[0]
	item_list = []
	index = -1
	for row in item['items']:
		index += 1
		if row['primary_attribute']:
			attributes = row['attributes']
			for val in row['work_order_qty'].keys():
				attributes[row['primary_attribute']] = val
				item1 = {}
				item_name = row['name']
				tup = tuple(sorted(attributes.items()))
				variant_name = get_or_create_ipd_variant(item_variants, item_name, tup, attributes)
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
				item1['quantity'] = row['work_order_qty'][val]
				item1['row_index'] = index
				item1['table_index'] = index
				item1['set_combination'] = row['item_keys']
				i = False
				for value in row['work_order_qty'].keys():
					if row['work_order_qty'][value]:
						i = True
						break
				if i or deliverable:
					item_list.append(item1)
		else:
			item1 = {}
			item_name = row['name']
			attributes = row['attributes']
			tup = tuple(sorted(attributes.items()))
			variant_name = get_or_create_ipd_variant(item_variants, item_name, tup, attributes)
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
			item1['quantity'] = row['work_order_qty']
			item1['table_index'] = index
			item1['row_index'] = index
			item1['set_combination'] = row['item_keys']
			if item1['quantity'] or deliverable:
				item_list.append(item1)
	ipd_doc.db_set("variants_json", json.dumps(item_variants), update_modified=False)
	return item_list

def get_item_structure(items,item_name, process, uom):
	item_list = {
		item_name: []
	}
	row_index = 0
	table_index = 0
	for item in items:
		row_index = item['row_index']
		table_index = item['table_index']
		item_list[item_name].append({
			"item_variant":item['item_variant'],
			"qty":item['quantity'],
			"process":process,
			"uom":uom,
			"row_index":row_index,
			"table_index":table_index,
			"set_combination":item['set_combination']
		})
	return item_list, row_index, table_index	

def get_bom_structure(items, row_index, table_index):
	bom = {}
	for item_name,values in items.items():
		table_index = table_index + 1
		for item,value in values.items():
			row_index = row_index + 1
			if not bom.get(item_name):
				bom[item_name] = []

			bom[item_name].append({
				"item_variant":item,
				"qty":value[0],
				"process":value[1],
				"uom":value[2],
				"row_index":row_index,
				"table_index":table_index
			})

	return bom

@frappe.whitelist()
def add_comment(doc_name, date, reason):
	doc = frappe.get_doc('Work Order', doc_name)
	text = f"Delivery date changed from {doc.expected_delivery_date} to {date} <br> Reason: {reason}"
	doc.expected_delivery_date = date
	doc.add_comment('Comment',text=text)
	doc.save()
	
@frappe.whitelist()
def update_stock(work_order):
	logger = get_module_logger("work_order")
	logger.debug(f"{work_order} data construction {datetime.now()}")
	res = get_variant_stock_details()
	sl_entries = []
	doc = frappe.get_doc("Work Order", work_order)
	received_type = frappe.db.get_single_value("Stock Settings","default_received_type")
	for data in doc.deliverables:
		if (data.qty - data.stock_update) > 0 and res.get(data.item_variant):
			reduce_qty = 0
			if data.stock_update == 0:
				reduce_qty = data.qty - data.pending_quantity
			else:
				reduce_qty = data.qty - data.pending_quantity - data.stock_update
			if reduce_qty > 0:	
				sl_entries.append({
					"item": data.item_variant,
					"warehouse": doc.supplier,
					"lot": doc.lot,
					"received_type":received_type,
					"voucher_type": doc.doctype,
					"voucher_no": work_order,
					"voucher_detail_no": data.name,
					"qty": reduce_qty * -1,
					"uom": data.uom,
					"rate": data.rate,
					"is_cancelled": 1 if data.docstatus == 2 else 0,
					"posting_date": nowdate(),
					"posting_time": nowtime(),
				})
			data.stock_update = data.qty
	logger.debug(f"{work_order} data construction completed {datetime.now()}")

	make_sl_entries(sl_entries)
	logger.debug(f"{work_order} SLE Updated {datetime.now()}")
	doc.open_status = "Close"
	doc.is_delivered = True
	doc.total_quantity = 0
	doc.save()

@frappe.whitelist()
def calculate_completed_pieces(doc_name):
	wo_doc = frappe.get_doc("Work Order", doc_name)
	from production_api.production_api.doctype.cutting_plan.cutting_plan import get_complete_incomplete_structure
	for item in wo_doc.work_order_calculated_items:
		item.received_qty = 0
	cut_process = frappe.get_value("Item Production Detail", wo_doc.production_detail, "cutting_process")	
	if cut_process == wo_doc.process_name:
		items = fetch_order_item_details(wo_doc.work_order_calculated_items, wo_doc.production_detail)
		complete, incomplete = get_complete_incomplete_structure(wo_doc.production_detail, items)
		wo_doc.set("completed_items_json", complete)
		wo_doc.set("incompleted_items_json",incomplete)
	else:
		wo_doc.set("completed_items_json", {})
		wo_doc.set("incompleted_items_json",{})	
	wo_doc.save()
	# calc(doc_name)
	frappe.enqueue(calc,"short", doc_name=doc_name)	
	
def calc(doc_name):	
	grn_list = frappe.get_list("Goods Received Note", filters={"against_id": doc_name,"docstatus": 1}, pluck="name")
	from production_api.production_api.doctype.goods_received_note.goods_received_note import calculate_pieces
	for grn in grn_list:
		calculate_pieces(grn)

def update_if_string_instance(obj):
	if isinstance(obj, string_types):
		obj = json.loads(obj)

	if not obj:
		obj = {}

	return obj	

@frappe.whitelist()
def fetch_summary_details(doc_name, production_detail):
	ipd_doc = frappe.get_doc("Item Production Detail", production_detail)
	wo_doc = frappe.get_doc("Work Order", doc_name)
	item_details = []
	items = wo_doc.work_order_calculated_items
	items = sorted(items, key = lambda i: i.row_index)
	for key, variants in groupby(items, lambda i: i.row_index):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0].item_variant)
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			"item_keys": {},
			"is_set_item": ipd_doc.is_set_item,
			"set_attr": ipd_doc.set_item_attribute,
			"pack_attr": ipd_doc.packing_attribute,
			"major_attr_value": ipd_doc.major_attribute_value,
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			"dependent_attribute": current_item_attribute_details['dependent_attribute'],
			"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
			'values': {},
		}

		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0}
			for variant in variants:
				set_combination = variant.set_combination
				if isinstance(set_combination, string_types):
					set_combination = json.loads(set_combination)
				if set_combination:
					if set_combination.get("major_part"):
						item['item_keys']['major_part'] = set_combination.get("major_part")

					if set_combination.get("major_colour"):
						item['item_keys']['major_colour'] = set_combination.get("major_colour")		

				current_variant = frappe.get_cached_doc("Item Variant", variant.item_variant)
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'qty': variant.quantity,
							"delivered": variant.delivered_quantity,
							"received": variant.received_qty
						}
						break
		else:
			item['values']['default'] = {
				'qty': variants[0].quantity,
				"delivered": variants[0].delivered_quantity,
				"received": variants[0].received_qty
			}
			
		index = get_item_group_index(item_details, current_item_attribute_details)
		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				"dependent_attribute": current_item_attribute_details['dependent_attribute'],
				"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
				'additional_parameters': current_item_attribute_details['additional_parameters'],
				"is_set_item": ipd_doc.is_set_item,
				"set_attr": ipd_doc.set_item_attribute,
				"pack_attr": ipd_doc.packing_attribute,
				"major_attr_value": ipd_doc.major_attribute_value,
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)

	deliverables = fetch_item_details(wo_doc.deliverables, wo_doc.production_detail )

	return {
		"item_detail":item_details,
		"deliverables": deliverables
	}