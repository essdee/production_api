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
from production_api.utils import get_stich_details, get_part_list, update_if_string_instance, get_tuple_attributes
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_calculated_bom, calculate_accessory, get_cloth_combination, get_stitching_combination

class WorkOrder(Document):
	def on_update_after_submit(self):
		if self.is_rework:
			frappe.publish_realtime("get_receivables_data")
		check_quantity = True
		for item in self.deliverables:
			if flt(item.pending_quantity) > flt(0):
				check_quantity = False
				break

		if check_quantity and self.deliverables:
			self.set('is_delivered',1)

	def before_submit(self):
		if len(self.deliverables) == 0:
			frappe.throw("There is no deliverables on the Work Order")
		
		if len(self.receivables) == 0:
			frappe.throw("There is no receivables on the Work Order")

	def on_submit(self):
		d = [{
			"from_date": self.planned_start_date,
			"to_date": self.expected_delivery_date,
			"reason": None,
			"user": frappe.session.user
		}]
		self.set("work_order_tracking_logs", d)
		self.update_deliverables()

	def on_cancel(self):
		self.update_deliverables()

	def update_deliverables(self):
		if self.is_rework:
			for item in self.deliverables:
				grn_details = item.grn_detail_no.split(",")
				qty = item.qty
				for grn in grn_details:
					grn = grn.strip()
					quantity, rework_quantity = frappe.get_value("Goods Received Note Item", grn, ["quantity", "rework_quantity"])
					update_qty = 0
					valid_qty = 0
					if self.docstatus == 1:
						valid_qty = quantity - rework_quantity
						update_qty = rework_quantity + valid_qty
						qty = qty - valid_qty
					else:
						if qty >= rework_quantity:
							qty = qty - rework_quantity
						else:
							update_qty = rework_quantity - qty
							qty = qty - update_qty
					frappe.db.sql(f"UPDATE `tabGoods Received Note Item` SET rework_quantity = {update_qty} WHERE name = '{grn}'")

	def onload(self):
		if not self.is_new():
			cp = frappe.get_value("Item Production Detail", self.production_detail, "cutting_process")
			if cp == self.process_name:
				self.set_onload("is_cutting", True)
			else:
				self.set_onload("is_cutting", False)

		if self.is_rework:
			deliverable_item_details = fetch_rework_item_details(self.get('deliverables'),self.production_detail)
			self.set_onload('deliverable_item_details', deliverable_item_details)
		else:	
			deliverable_item_details = fetch_item_details(self.get('deliverables'),self.production_detail, is_calc=True)
			self.set_onload('deliverable_item_details', deliverable_item_details)

		receivable_item_details = fetch_item_details(self.get('receivables'),self.production_detail, include_id=True)
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
			if not self.is_rework:
				if(self.get('deliverable_item_details')):
					items = save_item_details(self.deliverable_item_details)
					self.set("deliverables",items)

			if(self.get('receivable_item_details')):
				items = save_item_details(self.receivable_item_details, supplier=self.supplier, process_name=self.process_name)
				self.set("receivables",items)
			
			if len(self.receivables) > 0:
				self.calc_receivable_rate()
			planned_qty = 0	
			for row in self.work_order_calculated_items:
				planned_qty += row.get('quantity', 0)
			self.planned_quantity = planned_qty	
		else:
			self.set("deliverables",[])
			self.set("receivables",[])	
			self.set("work_order_calculated_items",[])

	def calc_receivable_rate(self):	
		if self.rework_type == "No Cost":
			return	
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
					SELECT packing_process, stiching_process, cutting_process FROM `tabItem Production Detail`
					WHERE name = '{self.production_detail}'
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
			if self.is_rework:
				return
			del fil['supplier']
			docnames = frappe.get_list('Process Cost',filters = fil)
			if docnames:
				docname = docnames[0]['name']
		if not docname and not self.is_rework:
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
				if attributes.get(ipd_doc.stiching_attribute):
					rate = rate/stich_details[attributes.get(ipd_doc.stiching_attribute)]
			row.cost = round(rate,2)
			row.total_cost = round((rate * row.qty), 2)

def save_item_details(item_details, supplier=None, process_name = None):
	item_details = update_if_string_instance(item_details)
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
					variant = get_or_create_variant(item_name, item_attributes)
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
					variant = get_or_create_variant(item_name, item_attributes)
					item1 = get_data(item,table_index,row_index, process_name, quantity,cost)	
					item1['item_variant'] = variant
					item1['set_combination'] = item['values']['default'].get('set_combination', {})
					item1['secondary_qty'] = item['values']['default'].get('secondary_qty')
					if not supplier:
						item1['is_calculated'] = item['values']['default'].get('is_calculated') or 0
					item1['secondary_uom'] = item.get('secondary_uom')
					items.append(item1)
			row_index += 1
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

def fetch_rework_item_details(items_list, ipd, is_dc=False):
	grouped_items = {}
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)	
	items_list = [item.as_dict() for item in items_list]
	for received_type, items in groupby(items_list, lambda i: i['item_type']):
		items = list(items)
		item_details = []
		items = sorted(items, key = lambda i: i['row_index'])
		for key, variants in groupby(items, lambda i: i['row_index']):
			variants = list(variants)
			current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
			current_item_attribute_details = get_attribute_details(current_variant.item)
			check = False
			if is_dc:
				for variant in variants:
					if variant['pending_quantity'] > 0:
						check = True
						break
			else:
				check = True
			if check:	
				item = {
					'name': current_variant.item,
					'lot': variants[0]['lot'],
					'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
					"is_set_item": ipd_doc.is_set_item,
					"pack_attr":ipd_doc.packing_attribute,
					"set_attr":ipd_doc.set_item_attribute,
					"major_attr_value": ipd_doc.major_attribute_value,
					'primary_attribute': current_item_attribute_details['primary_attribute'],
					"dependent_attribute": current_item_attribute_details['dependent_attribute'],
					"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
					'values': {},
					'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
				}
				if item['primary_attribute']:
					for variant in variants:
						current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
						for attr in current_variant.attributes:
							if attr.attribute == item.get('primary_attribute'):
								item['values'][attr.attribute_value] = {
									'qty': round(variant['qty']) if variant['qty'] else 0,
									'pending_quantity': round(variant['pending_quantity']) if variant['pending_quantity'] else 0,
									'delivered_quantity': 0,
									'set_combination':variant['set_combination'],
									"row_index": variant['row_index'],
									"table_index": variant['table_index'],
									"uom": variant['uom'],
									"grn_detail_no": variant['grn_detail_no'],
									"cost": 0,
									"total_cost": 0,
									"ref_doctype":"Work Order Deliverables",
									"ref_docname": variant.get('name', None),
									"comments": "",
								}
								if is_dc:
									item['values'][attr.attribute_value]['qty'] = round(variant['pending_quantity']) if variant['pending_quantity'] else 0
								break
				index = get_item_group_index(item_details, current_item_attribute_details)
				if index == -1:
					item_details.append({
						'attributes': current_item_attribute_details['attributes'],
						'primary_attribute': current_item_attribute_details['primary_attribute'],
						'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
						"dependent_attribute": current_item_attribute_details['dependent_attribute'],
						"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
						'items': [item]
					})
				else:
					item_details[index]['items'].append(item)
		grouped_items[received_type] = item_details
	return grouped_items

def fetch_item_details(items,ipd, include_id = False, is_grn= False, is_calc=False):
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
							'qty': round(variant.qty, 3) if variant.qty else 0,
							'secondary_qty': round(variant.secondary_qty, 3) if variant.secondary_qty else 0,
							'pending_qty': round(variant.pending_quantity, 3) if variant.pending_quantity else 0,
							'cancelled_qty': round(variant.cancelled_qty, 3) if variant.cancelled_qty else 0,
							'rate': variant.rate,
							'tax': variant.tax,
							'cost': round(variant.cost, 2) if variant.cost else variant.cost,
							'set_combination':variant.set_combination,
						}
						if is_calc:
							item['values'][attr.attribute_value]['is_calculated'] = variant.is_calculated
						if is_grn:
							item['values'][attr.attribute_value]['qty'] = round(variant.pending_quantity,0)
							item['values'][attr.attribute_value]['rate'] = round(variant.cost, 2) if variant.cost else variant.cost
							
						if include_id:
							item['values'][attr.attribute_value]['ref_doctype'] = "Work Order Receivables"
							item['values'][attr.attribute_value]['ref_docname'] = variant.name
						break
		else:
			item['values']['default'] = {
				'qty': round(variants[0].qty, 3) if variants[0].qty else variants[0].qty,
				'secondary_qty': round(variants[0].secondary_qty, 3) if variants[0].secondary_qty else 0,
				'pending_qty': round(variants[0].pending_quantity, 3) if variants[0].pending_quantity else 0,
				'cancelled_qty': round(variants[0].cancelled_qty, 3) if variants[0].cancelled_qty else 0,
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
	data = fetch_item_details(wo.receivables,wo.production_detail, include_id=True, is_grn= is_grn)
	return data
 
@frappe.whitelist()
def get_lot_items(lot, doc_name, process, includes_packing=False):
	logger = get_module_logger("work_order")
	logger.debug(f"{doc_name} Calculation Started {datetime.now()}")
	doc = frappe.get_cached_doc("Lot", lot)	
	items = fetch_order_item_details(doc.lot_order_details, doc.production_detail, process=process, includes_packing=includes_packing)
	logger.debug(f"{doc_name} Fetched Order detail from Lot {datetime.now()}")
	return items

@frappe.whitelist()
def get_deliverable_receivable( items, doc_name, deliverable=False, receivable=False):
	logger = get_module_logger("work_order")
	logger.debug(f"{doc_name} Deliverable and Receivable Calculation {datetime.now()}")
	wo_doc = frappe.get_doc("Work Order", doc_name)
	lot_doc = frappe.db.sql(
		f"""
			SELECT production_detail, packing_uom, uom, pack_in_stage FROM `tabLot` WHERE name = '{wo_doc.lot}'
		""", as_dict=True
	)[0]
	ipd = lot_doc.production_detail
	uom = lot_doc.packing_uom
	pack_out_uom = lot_doc.uom
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	dept_attribute = ipd_doc.dependent_attribute
	pack_out_stage = ipd_doc.pack_out_stage
	stiching_in_stage = ipd_doc.stiching_in_stage
	wo_colour_sets = get_report_data(items, dept_attribute, ipd_doc.packing_attribute)
	items = get_items(items, deliverable=deliverable)
	if not items:
		frappe.throw("Enter the Qty to Calculate the Items")
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
		deliverables , y,z= calc_deliverable_and_receivable(ipd_doc, first_process, item_list, item_name, dept_attribute, ipd, wo_doc.lot, uom, bom, lot_doc, stiching_in_stage, pack_out_stage, pack_out_uom)
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
		receivables, total_qty, table_index, row_index = get_receivables(item_list, lot, uom)
		stiching_attributes = get_attributes(item_list, item_name, stiching_in_stage, dept_attribute, ipd)
		stiching_attributes.update(bom)
		deliverables  = get_deliverables(stiching_attributes, lot)
		accessory = get_accessories(item_list, ipd_doc)
		accessory = get_converted_accessory(ipd_doc, accessory, lot, table_index, row_index)
		deliverables = deliverables + accessory
	
	elif ipd_doc.packing_process == process:
		packing_attributes = get_attributes(item_list, item_name, pack_out_stage, dept_attribute, pack_ipd=ipd)
		item_list.update(bom)
		deliverables  = get_deliverables(item_list, lot)
		item_doc = frappe.get_cached_doc("Item", item_name)
		receivables, total_qty, table_index, row_index = get_receivables(packing_attributes, lot, uom, conversion_details=item_doc.uom_conversion_details, out_uom=pack_out_uom)
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
		accessory = get_accessories(item_list, ipd_doc)
		receivables, total_qty, table_index, row_index = get_receivables(cutting_attributes, lot, uom)
		accessory = get_converted_accessory(ipd_doc, accessory, lot, table_index, row_index)
		receivables = receivables + accessory
		deliverables  =  get_deliverables(bom, lot)
	else:	
		for item in ipd_doc.ipd_processes:
			if item.process_name == process:
				if ipd_doc.stiching_in_stage == item.stage:
					attributes = get_attributes(item_list, item_name, item.stage, dept_attribute, ipd, process)
					x = attributes.copy()
					x.update(bom)
					deliverables  = get_deliverables(x, lot)
					receivables, total_qty, table_index, row_index = get_receivables(attributes, lot, uom)
				
				elif lot_doc.pack_in_stage == item.stage:
					deliverables = item_list.copy()
					receivables, total_qty, table_index, row_index = get_receivables(deliverables,lot, uom)
					item_list.update(bom)
					deliverables = get_deliverables(item_list, lot)

				else:
					attributes = get_attributes(item_list, item_name, item.stage, dept_attribute, pack_ipd=ipd)
					receivables, total_qty, table_index, row_index = get_receivables(attributes,lot, uom)
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

def get_converted_accessory(ipd_doc, accessory, lot, table_index, row_index):
	accessories = []
	cloth_detail = {}
	for cloth in ipd_doc.cloth_detail:
		cloth_detail[cloth.name1] = cloth.cloth
	accessory_detail = {}
	for acc, qty in accessory.items():
		cloth_type, colour, dia = acc
		cloth_name = cloth_detail[cloth_type]
		uom = frappe.get_value("Item", cloth_name,"default_unit_of_measure")
		variant_name = get_or_create_variant(cloth_name, {ipd_doc.packing_attribute: colour, "Dia": dia})
		accessory_detail.setdefault(variant_name, {"uom": uom, "qty": 0})
		accessory_detail[variant_name]["qty"] += qty

	for variant, details in accessory_detail.items():
		accessories.append({
			'item_variant': variant , 
			'lot': lot, 
			'qty': details['qty'], 
			'uom': details['uom'], 
			'table_index': table_index, 
			'row_index': row_index, 
			'pending_quantity': details['qty'], 
			'set_combination': {},
			"is_accessory": True,
		})
		table_index += 1
		row_index += 1
	return accessories	

def get_report_data(items, dept_attribute, pack_attr):
	attrs = []
	set_attrs = []
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
			set_attrs.append(item['item_keys']['major_colour'])
		else:
			all_attrs = False	
	if all_attrs:
		wo_colour_sets = "All"
	else:	
		attributes = []
		idx = 0
		for attr in attrs:
			attribute = ""
			colour = None
			for key in attr:
				if key != dept_attribute:
					attribute += attr[key] + "-"
				if key == pack_attr:
					colour = attr[key]

			if attribute:		
				attribute = attribute[:-1]
				if colour != set_attrs[idx]:
					attribute += f"({set_attrs[idx]})"		
				attributes.append(attribute)
			idx += 1
		wo_colour_sets = ", ".join(attributes)	
	return wo_colour_sets

def get_receivables(items,lot, uom, conversion_details = None, out_uom = None):
	receivables = []
	total_qty = 0
	table_index = 0
	row_index = 0
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
			table_index = variant['table_index']
			row_index = variant['row_index']

	return receivables, total_qty, int(table_index)+1, int(row_index)+1	

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
	part_list = []
	stiching_combination = None
	if ipd:
		from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_stitching_combination
		ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
		stiching_combination = get_stitching_combination(ipd_doc)

	if pack_ipd:
		ipd_pack_doc = frappe.get_cached_doc("Item Production Detail", pack_ipd)
		if ipd_pack_doc.is_set_item:
			part_list = get_part_list(ipd_pack_doc)

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
				panel_colour_combination = get_panel_colour_combination(ipd_doc)
				if ipd_doc.is_set_item:
					part = None
					for attr in current_variant.attributes:
						if attr.attribute == ipd_doc.set_item_attribute:
							part = attr.attribute_value
							break
					set_item_stitching_attrs = get_stich_details(ipd_doc)
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
						m_colour = variant['set_combination']['major_colour']
						attributes[ipd_doc.packing_attribute] = panel_colour_combination[m_colour][item.stiching_attribute_value]	
						v = True
						panel_part = set_item_stitching_attrs[item.stiching_attribute_value]
						if panel_part != part:
							v = False							
						if v:
							new_variant = get_or_create_variant(itemname, attributes)
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
						
						new_variant = get_or_create_variant(itemname, attributes)
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
	return item_list

def get_receivable_item_attribute_details(variant, item_attributes, stage):
	attribute_details = {}
	for attr in variant.attributes:
		if attr.attribute in item_attributes['dependent_attribute_details']['attr_list'][stage]['attributes']:
			attribute_details[attr.attribute] = attr.attribute_value
	return attribute_details

def get_items(items, deliverable):
	items = update_if_string_instance(items)
	if len(items[0]['items']) == 0:
		return []
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
				variant_name = get_or_create_variant(item_name, attributes)
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
			variant_name = get_or_create_variant(item_name, attributes)
			item1['item_variant'] = variant_name
			item1['quantity'] = row['work_order_qty']
			item1['table_index'] = index
			item1['row_index'] = index
			item1['set_combination'] = row['item_keys']
			if item1['quantity'] or deliverable:
				item_list.append(item1)
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
	doc.append("work_order_tracking_logs", {
		"from_date": nowdate(),
		"to_date": date,
		"reason": reason,
		"user": frappe.session.user,
	})
	doc.expected_delivery_date = date
	doc.save()
	
@frappe.whitelist()
def update_stock(work_order):
	from production_api.mrp_stock.utils import get_stock_balance
	logger = get_module_logger("work_order")
	logger.debug(f"{work_order} data construction {datetime.now()}")
	res = get_variant_stock_details()
	sl_entries = []
	doc = frappe.get_doc("Work Order", work_order)
	grn_list = frappe.get_all('Goods Received Note', {"docstatus": 1, "against_id": work_order}, pluck="name")
	if not grn_list:
		frappe.throw("There is no Goods Received for this Work Order")

	dc_list = frappe.get_all("Delivery Challan", filters={
		"work_order": work_order, 
		"docstatus": 1,
		"is_internal_unit": 1,
		"transfer_complete": 0,
	}, limit=1, pluck="name")
	if dc_list:
		frappe.throw(_("Delivery Challan {0} is not completed. Please complete the Delivery Challan before Close Work Order.").format(dc_list[0]))
	grn_list = frappe.get_all("Goods Received Note", filters={
		"against": "Work Order",
		"against_id": work_order, 
		"docstatus": 1,
		"is_internal_unit": 1,
		"transfer_complete": 0,
	}, limit=1, pluck="name")
	if grn_list:
		frappe.throw(_("GRN {0} is not completed. Please complete the GRN before Close Work Order.").format(grn_list[0]))
	
	received_type = frappe.db.get_single_value("Stock Settings","default_received_type")
	for data in doc.deliverables:
		if (data.qty - data.pending_quantity - data.stock_update) > 0 and res.get(data.item_variant):
			reduce_qty = data.qty - data.pending_quantity - data.stock_update
			balance = get_stock_balance(data.item_variant, doc.supplier, received_type, lot=doc.lot)
			if reduce_qty > balance:
				reduce_qty = balance
			if reduce_qty:	
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
	process_name = wo_doc.process_name
	ipd_doc = frappe.get_doc("Item Production Detail", wo_doc.production_detail)
	if process_name in [ipd_doc.cutting_process, ipd_doc.stiching_process, ipd_doc.packing_process]:
		lot_doc = frappe.get_cached_doc("Lot",wo_doc.lot)
		field = "cut_qty" if process_name == ipd_doc.cutting_process else "stich_qty" if process_name == ipd_doc.stiching_process else "pack_qty"
		for item in wo_doc.work_order_calculated_items:
			for lot_item in lot_doc.lot_order_details:
				if lot_item.item_variant == item.item_variant and item.quantity > 0:
					setattr(lot_item, field, 0)	
					break

		lot_doc.save(ignore_permissions=True)

	for item in wo_doc.work_order_calculated_items:
		item.received_qty = 0
		item.received_type_json = {}
		item.delivered_quantity = 0	
			
	wo_doc.total_no_of_pieces_delivered = 0
	wo_doc.total_no_of_pieces_received = 0	
	wo_doc.received_types_json = {}
	processes = [ipd_doc.cutting_process]
	dc_processes = [ipd_doc.stiching_process]		
	for item in ipd_doc.ipd_processes:
		if item.process_name == wo_doc.process_name:
			if ipd_doc.stiching_in_stage == item.stage:
				processes.append(item.process_name)
				dc_processes.append(item.process_name)
				break
	all_process = processes + dc_processes
	if wo_doc.process_name in all_process:
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
	wo_doc.save()
	# calc(doc_name)
	frappe.enqueue(calc,"short", doc_name=doc_name)	
	
def calc(doc_name):	
	grn_list = frappe.get_list("Goods Received Note", filters={"against_id": doc_name,"docstatus": 1}, pluck="name")
	from production_api.production_api.doctype.goods_received_note.goods_received_note import calculate_pieces as calculate_grn_pieces
	for grn in grn_list:
		calculate_grn_pieces(grn)
	dc_list = frappe.get_list("Delivery Challan", filters={"work_order": doc_name,"docstatus": 1}, pluck="name")
	from production_api.production_api.doctype.delivery_challan.delivery_challan import calculate_pieces as calculate_dc_pieces
	for dc in dc_list:
		calculate_dc_pieces(dc)

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
				set_combination = update_if_string_instance(variant.set_combination)
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

	for item in item_details[0]['items']:
		total_qty = 0
		total_delivered = 0
		total_received = 0
		for primary_attr in item_details[0]['primary_attribute_values']:
			if item['values'][primary_attr].get("qty"):
				total_qty += item['values'][primary_attr]['qty']
			if item['values'][primary_attr].get("delivered"):
				total_delivered += item['values'][primary_attr]['delivered']
			if item['values'][primary_attr].get("received"):
				total_received += item['values'][primary_attr]['received']
		item['total_qty'] = total_qty
		item['total_delivered'] = total_delivered
		item['total_received'] = total_received	

	deliverables = fetch_item_details(wo_doc.deliverables, wo_doc.production_detail )

	return {
		"item_detail":item_details,
		"deliverables": deliverables
	}

def get_accessories(item_list, ipd_doc):
	cloth_combination = get_cloth_combination(ipd_doc)
	attrs = None
	stitching_combination = get_stitching_combination(ipd_doc)
	cloth_detail = []
	from production_api.production_api.doctype.goods_received_note.goods_received_note import get_variant_attributes
	for item in item_list:
		for variant in item_list[item]:
			variant_doc = frappe.get_cached_doc("Item Variant", variant['item_variant'])
			attrs = get_variant_attributes(variant_doc)
			accessory_detail = calculate_accessory(ipd_doc, cloth_combination, stitching_combination, attrs, variant['qty'])
			cloth_detail = cloth_detail + accessory_detail

	cloth_dict = {}
	for cloth in cloth_detail:
		key = (cloth['cloth_type'], cloth['colour'], cloth['dia'])
		cloth_dict.setdefault(key, 0)
		cloth_dict[key] += cloth['quantity']
	return cloth_dict

from production_api.production_api.doctype.purchase_order.purchase_order import get_address_display
@frappe.whitelist()
def get_grn_rework_items(doc_name):
	grn_list = frappe.get_all("Goods Received Note", filters={
		"against":"Work Order", 
		"docstatus": 1, 
		"against_id": doc_name,
		"is_return": ["=", 0]
	}, pluck="name")
	wo_doc = frappe.get_doc("Work Order", doc_name)
	if not grn_list:
		frappe.msgprint("No GRN found for this work order")
		return None
	items = {}
	for grn in grn_list:
		doc = frappe.get_doc("Goods Received Note",grn)
		for item in doc.items:
			received_type = item.received_type
			grn_type = frappe.get_value("GRN Item Type",received_type,"type")
			if (grn_type == "Mistake" or grn_type =="Rejected") and (item.quantity - item.rework_quantity > 0):
				items.setdefault(received_type, {})
				set_combination = update_if_string_instance(item.get('set_combination'))
				set_key = tuple(sorted(set_combination.items()))
				items[received_type].setdefault((item.get('item_variant'), set_key), {
					"qty": 0,
					"uom": item.get('uom'),
					"grn_detail_no": [],
				})
				items[received_type][(item.get('item_variant'), set_key)]['qty'] += item.quantity
				items[received_type][(item.get('item_variant'), set_key)]['grn_detail_no'].append(item.name)

	grouped_items = {}
	for received_type, item_variants in items.items():
		grouped_items[received_type] = {}
		for (item_variant, set_comb), details in item_variants.items():
			doc = frappe.get_cached_doc("Item Variant", item_variant)
			primary_attr = frappe.get_value("Item", doc.item, "primary_attribute")
			attrs = get_variant_attr_values(doc, primary_attr)
			key = (doc.item, attrs)
			if key not in grouped_items[received_type]:
				grouped_items[received_type][key] = []
			d = {
				"item_variant": item_variant,
				"set_combination": set_comb,
			}	
			d.update(details)
			grouped_items[received_type][key].append(d)

	deliverables = {}
	table_index = 0
	row_index = 0
	for received_type, item_variant_details in grouped_items.items():
		for item_variant_key, details in item_variant_details.items():
			items = grouped_items[received_type][item_variant_key]
			for item in items:
				deliverables.setdefault(received_type, [])
				deliverables[received_type].append({
					"item_variant": item['item_variant'],
					"set_combination": get_tuple_attributes(item['set_combination']),
					"lot": wo_doc.lot,
					"qty": item['qty'],
					"uom": item['uom'],
					"rework_quantity": 0,
					"grn_detail_no": ", ".join(item['grn_detail_no']),
					"table_index": table_index,
					"row_index": row_index,
					"cost": 0,
					"total_cost": 0,
				})	
			row_index += 1
	pop_up_details = {}
	for received_type, items in deliverables.items():
		received_items = fetch_rework_popup_items(items, wo_doc.production_detail)
		pop_up_details[received_type] = received_items
	return  pop_up_details

def fetch_rework_popup_items(items, ipd):
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
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			"dependent_attribute": current_item_attribute_details['dependent_attribute'],
			"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
			'values': {},
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						item['values'][attr.attribute_value] = {
							'qty': round(variant['qty']) if variant['qty'] else 0,
							'rework_quantity': round(variant['rework_quantity']) if variant['rework_quantity'] else 0,
							'set_combination':variant['set_combination'],
							"row_index": variant['row_index'],
							"table_index": variant['table_index'],
							"uom": variant['uom'],
							"grn_detail_no": variant['grn_detail_no'],
							"cost": 0,
							"total_cost": 0,
						}
						break
		index = get_item_group_index(item_details, current_item_attribute_details)
		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				"dependent_attribute": current_item_attribute_details['dependent_attribute'],
				"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	return item_details

@frappe.whitelist()
def create_rework(doc_name, items, supplier,supplier_address, rework_type, supplier_type):
	items = update_if_string_instance(items)
	wo_doc = frappe.get_doc("Work Order", doc_name)
	process_name = wo_doc.process_name
	deliverables = []
	for received_type in items:
		item_details = update_if_string_instance(items[received_type])
		for group in item_details:
			for item in group['items']:
				item_name = item['name']
				item_attributes = item['attributes']
				if(item.get('primary_attribute')):
					for attr, values in item['values'].items():
						quantity = values.get('qty')
						if not quantity:
							quantity = 0
						if not values.get("rework_quantity") > 0:
							continue
						item_attributes[item.get('primary_attribute')] = attr
						cost = values.get('cost', 0)
						variant = get_or_create_variant(item_name, item_attributes)
						item1 = get_data(item, values.get("table_index"), values.get("row_index"), process_name, quantity, cost)
						item1['item_variant'] = variant	
						item1['set_combination'] = values.get("set_combination", {})
						item1['secondary_qty'] = values.get('secondary_qty', None)
						item1['secondary_uom'] = values.get('secondary_uom', None)
						item1["lot"] = wo_doc.lot
						item1["uom"] = values.get('uom')
						item1['qty'] = values.get("rework_quantity")
						item1['grn_detail_no'] = values.get('grn_detail_no')
						item1['table_index'] = values.get("table_index")
						item1['row_index'] = values.get("row_index")
						item1['item_type'] = received_type
						item1['cost'] = 0
						item1['total_cost'] = 0
						deliverables.append(item1)
	x = frappe.new_doc("Work Order")	
	x.is_rework = True
	x.parent_wo = doc_name
	x.production_detail = wo_doc.production_detail
	x.naming_series = "WO-"
	x.supplier = supplier
	x.delivery_location = wo_doc.delivery_location
	x.process_name = wo_doc.process_name
	x.planned_start_date = wo_doc.planned_start_date
	x.planned_end_date = wo_doc.planned_end_date
	x.expected_delivery_date = wo_doc.expected_delivery_date
	x.item = wo_doc.item
	x.lot = wo_doc.lot
	x.supplier_address = supplier_address
	x.supplier_address_details = get_address_display(supplier_address)
	x.delivery_address = wo_doc.delivery_address
	x.delivery_address_details = get_address_display(wo_doc.delivery_address)
	x.open_status = "Open"
	x.rework_type = rework_type
	x.supplier_type = supplier_type
	x.set("deliverables",deliverables)
	receivables = {}
	for item in deliverables:
		set_comb = update_if_string_instance(item['set_combination'])
		tup = tuple(sorted(set_comb.items()))
		receivables.setdefault((item['item_variant'], tup), {
			"set_combination" : item['set_combination'],
			"secondary_qty" : item['secondary_qty'],
			"secondary_uom" :item['secondary_uom'],
			"lot": item["lot"],
			"uom": item["uom"],
			"qty":0,
			"pending_quantity": 0,
			"table_index":item['table_index'],
			"row_index":item['row_index'],
			"cost":item['cost'],
			"total_cost":item['total_cost']
		})
		receivables[(item['item_variant'], tup)]["qty"] += item['qty']
		receivables[(item['item_variant'], tup)]["pending_quantity"] += item['qty']
	receivable_list = []
	for (item_variant, tup) in receivables:
		detail = receivables[(item_variant, tup)]
		detail['item_variant'] = item_variant
		receivable_list.append(detail)
	x.set("receivables",receivable_list)	
	x.save()	
	return x.name

def get_variant_attr_values(doc, primary_attr):
	attrs = []
	for attr in doc.attributes:
		if attr.attribute != primary_attr:
			attrs.append(attr.attribute_value)
	attrs.sort()
	if attrs:
		attrs = tuple(attrs)
	else:
		attrs = None			
	return attrs

@frappe.whitelist()
def update_receivables(receivables_data, doc_name):
	receivables_data = update_if_string_instance(receivables_data)
	for receivable in receivables_data:
		for item in receivable['items']:
			for val in item['values']:
				cost = item['values'][val]['cost']
				ref_docname = item['values'][val]['ref_docname'] 
				frappe.db.sql(
					"""
						UPDATE `tabWork Order Receivables` set cost = %(cost)s WHERE name = %(ref_docname)s
					""", {
						"cost": cost,
						"ref_docname": ref_docname,
					}
				)

def get_panel_colour_combination(ipd_doc):
	indexes = {}
	comb_details = {}
	for row in ipd_doc.stiching_item_combination_details:
		if indexes.get(row.index):
			major_colour = indexes[row.index]
			comb_details[major_colour][row.set_item_attribute_value] = row.attribute_value
		else:
			indexes[row.index] = row.major_attribute_value
			comb_details[row.major_attribute_value] = {}
			comb_details[row.major_attribute_value][row.set_item_attribute_value] = row.attribute_value

	return comb_details