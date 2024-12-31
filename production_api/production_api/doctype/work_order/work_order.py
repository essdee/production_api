# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

from frappe import _
import frappe, json, math
from six import string_types
from itertools import groupby
from frappe.model.document import Document
from frappe.utils import flt, nowdate, nowtime
from production_api.mrp_stock.stock_ledger import make_sl_entries
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_group_index
from production_api.production_api.doctype.item.item import get_attribute_details, get_or_create_variant
from production_api.essdee_production.doctype.lot.lot import fetch_order_item_details, get_uom_conversion_factor
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_calculated_bom
from production_api.production_api.doctype.delivery_challan.delivery_challan import get_variant_stock_details

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
		deliverable_item_details = fetch_item_details(self.get('deliverables'),process=self.process_name,is_calc=True)
		self.set_onload('deliverable_item_details', deliverable_item_details)

		receivable_item_details = fetch_item_details(self.get('receivables'),process=self.process_name)
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
				items = save_item_details(self.deliverable_item_details)
				self.set("deliverables",items)

			if(self.get('receivable_item_details')):
				frappe.flags.check = False
				items = save_item_details(self.receivable_item_details,supplier=self.supplier,process_name=self.process_name,doc=self.name,ipd=self.production_detail)
				self.set("receivables",items)

			if frappe.flags.check and len(self.receivables) > 0:
				self.calc_receivable_rate()
		else:
			self.set("deliverables",[])
			self.set("receivables",[])	

	def calc_receivable_rate(self):		
		for row in self.receivables:
			# doc = frappe.get_doc("Work Order", self.name)
			rate, cost_doc = get_rate_and_quantity(self.process_name, row.item_variant, row.qty, self, self.supplier)
			attr_qty = get_attributes_qty(self.production_detail, self.process_name, cost_doc)
			rate = rate/attr_qty
			row.cost = rate
			row.total_cost = rate * row.qty

def save_item_details(item_details, supplier=None, process_name = None, doc = None, ipd = None):
	if isinstance(item_details, string_types):
		item_details = json.loads(item_details)
	items = []
	if doc:
		doc = frappe.get_doc("Work Order", doc)
	row_index = 0
	for table_index, group in enumerate(item_details):
		for item in group['items']:
			item_name = item['name']
			item_attributes = item['attributes']
			if(item.get('primary_attribute')):
				for attr, values in item['values'].items():
					quantity = values.get('qty')
					if not quantity:
						quantity = 0
					item_attributes[item.get('primary_attribute')] = attr
					item1 = get_data(item,item_name,item_attributes,table_index,row_index, process_name, quantity, doc, ipd, supplier)	
					item1['secondary_qty'] = values.get('secondary_qty')
					item1['secondary_uom'] = values.get('secondary_uom')
					if not supplier:
						item1['is_calculated'] = values.get('is_calculated') or 0
					items.append(item1)
			else:
				if item['values'].get('default') and item['values']['default'].get('qty'):
					quantity = item['values']['default'].get('qty')
					item1 = get_data(item,item_name,item_attributes,table_index,row_index, process_name, quantity, doc, ipd, supplier)	
					item1['secondary_qty'] = item['values']['default'].get('secondary_qty')
					if not supplier:
						item1['is_calculated'] = item['values']['default'].get('is_calculated') or 0
					item1['secondary_uom'] = item.get('secondary_uom')
					items.append(item1)
			row_index += 1
	return items

def get_data(item, item_name, item_attributes, table_index, row_index, process_name, quantity, doc, ipd, supplier):
	item1 = {}
	variant_name = get_or_create_variant(item_name, item_attributes)
	if process_name:
		rate, cost_doc = get_rate_and_quantity(process_name,variant_name,quantity, doc, supplier)
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

def get_rate_and_quantity(process_name, variant_name, quantity, doc, supplier):
	item_doc = frappe.get_cached_doc('Item Variant',variant_name)
	item = item_doc.item
	fil = {
		'process_name':process_name,
		'item':item,
		'is_expired':0,
		'from_date':['<=',doc.wo_date],
		'docstatus': 1,
	}
	if supplier:
		fil['supplier'] = supplier

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
		frappe.throw('No process cost for ' + process_name)
	
	rate = 0
	order_quantity = 0
	low_price = 0
	found = False
	process_doc = frappe.get_cached_doc('Process Cost', docname)

	check_list = None
	if doc.is_rework and doc.rework_type == 'No Cost':
		return float(0),docname 
	if doc.is_rework:
		check_list = process_doc.rework_cost_values
	else:
		check_list = process_doc.process_cost_values	

	if process_doc.depends_on_attribute:
		attribute = process_doc.attribute
		attribute_value = next((attr.attribute_value for attr in item_doc.attributes if attr.attribute == attribute), None)
		for cost_values in check_list:
			cost = cost_values.as_dict()
			if cost['min_order_qty'] > quantity and cost['attribute_value'] == attribute_value:
				rate = cost['price']
				found = True
				break
			if order_quantity <= cost['min_order_qty'] and cost['attribute_value'] == attribute_value:
				order_quantity = cost['min_order_qty']
				low_price = cost['price']
	else:
		for cost_values in check_list:
			cost = cost_values.as_dict()
			if cost['min_order_qty'] > quantity:
				rate = cost['price']
				found = True
				break
			if order_quantity <= cost['min_order_qty']:
				order_quantity = cost['min_order_qty']
				low_price = cost['price']		
	if not found:
		return low_price, docname
	
	return rate, docname	

def fetch_item_details(items,process=None, include_id = False, is_grn= False, is_calc=False):
	items = [item.as_dict() for item in items]
	item_details = []
	if process == "Cutting" and is_calc:
		try:
			items = sorted(items, key=lambda i: i['item_variant'] if i['is_calculated'] else i['row_index'])
		except:
			items = sorted(items, key=lambda i: i['item_variant'])
	else:
		items = sorted(items, key = lambda i: i['row_index'])

	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
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
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
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
						if is_calc:
							item['values'][attr.attribute_value]['is_calculated'] = variant.is_calculated
						if is_grn:
							item['values'][attr.attribute_value]['qty'] = variant.pending_quantity
							item['values'][attr.attribute_value]['rate'] = variant.cost
							
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
			if is_calc:
				item['values']['default']['is_calculated'] = variants[0].is_calculated
			if include_id:
				item['values']['default']['ref_doctype'] = "Work Order Receivables"
				item['values']['default']['ref_docname'] = variants[0].name
			if is_grn:
				item['values']['default']['qty'] = variants[0].pending_quantity
				item['values']['default']['rate'] = variants[0].cost

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
	data = fetch_item_details(wo.receivables,process = wo.process_name, include_id=True, is_grn= is_grn)
	return data
 
@frappe.whitelist()
def get_lot_items(lot, process):
	doc = frappe.get_doc("Lot", lot)	
	items = fetch_order_item_details(doc.lot_order_details, doc.production_detail)
	return items

@frappe.whitelist()
def get_deliverable_receivable( lot, process, items, doc_name, supplier):
	lot_doc = frappe.get_cached_doc("Lot", lot)
	ipd = lot_doc.production_detail
	uom = lot_doc.packing_uom
	pack_out_uom = lot_doc.uom

	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	dept_attribute = ipd_doc.dependent_attribute
	pack_out_stage = ipd_doc.pack_out_stage
	stiching_in_stage = ipd_doc.stiching_in_stage
	items = get_items(items)
	grp_variant = items[0]['item_variant']
	item_name = frappe.get_value("Item Variant", grp_variant, 'item')
	item_list, row_index, table_index = get_item_structure(items, item_name, process, uom)
	deliverables = []
	receivables = []
	total_qty = 0
	doc = frappe.get_cached_doc("Work Order", doc_name)
	is_group = frappe.get_value("Process",process,"is_group")
	if is_group:
		b = {}
		first_process = None
		final_process = None
		process_doc = frappe.get_cached_doc("Process",process)
		for idx, p in enumerate(process_doc.process_details):
			m = get_calculated_bom(ipd, items, lot, process_name=p.process_name, doctype="Work Order")
			b.update(m)
			if idx == 0:
				first_process = p.process_name
			else:
				final_process = p.process_name

		bom = get_bom_structure(b,row_index, table_index)	
		item_list2 = item_list.copy()
		deliverables , y,x= 	calc_deliverable_and_receivable(ipd_doc, first_process, item_list, item_name, dept_attribute, ipd, lot, doc, uom, bom, lot_doc, stiching_in_stage, pack_out_stage, pack_out_uom, supplier, grp_process=process)
		x, receivables, total_qty = calc_deliverable_and_receivable(ipd_doc, final_process, item_list2, item_name, dept_attribute, ipd, lot, doc, uom, {}, lot_doc, stiching_in_stage, pack_out_stage, pack_out_uom, supplier,grp_process=process)		
	else:
		bom = get_calculated_bom(ipd, items, lot, process_name=process,doctype="Work Order")
		bom = get_bom_structure(bom, row_index, table_index)
		deliverables, receivables, total_qty = calc_deliverable_and_receivable(ipd_doc, process, item_list, item_name, dept_attribute, ipd, lot, doc, uom, bom, lot_doc, stiching_in_stage, pack_out_stage, pack_out_uom, supplier)		

	doc.set('deliverables',deliverables)
	doc.set('receivables', receivables)
	doc.set("total_quantity", total_qty)
	doc.save()
	return None

def calc_deliverable_and_receivable(ipd_doc, process, item_list, item_name, dept_attribute, ipd, lot, doc, uom, bom, lot_doc, stiching_in_stage, pack_out_stage, pack_out_uom, supplier, grp_process=None):
	deliverables = []
	receivables = []
	process_cost = process
	if grp_process:
		process_cost = grp_process
	total_qty = None
	if ipd_doc.stiching_process == process:
		receivables, total_qty  = get_receivables(item_list, process_cost, lot, uom, doc, supplier, ipd)
		stiching_attributes = get_attributes(item_list, item_name, stiching_in_stage, dept_attribute, ipd)
		stiching_attributes.update(bom)
		deliverables  = get_deliverables(stiching_attributes, lot)
	
	elif ipd_doc.packing_process == process:
		packing_attributes = get_attributes(item_list, item_name, pack_out_stage, dept_attribute)
		item_list.update(bom)
		deliverables  = get_deliverables(item_list, lot)
		item_doc = frappe.get_cached_doc("Item", item_name)
		receivables, total_qty  = get_receivables(packing_attributes, process_cost,lot, uom, doc, supplier, ipd, conversion_details=item_doc.uom_conversion_details, out_uom=pack_out_uom)
		
	elif ipd_doc.cutting_process == process:
		cutting_out_stage = frappe.get_value("Item Production Detail", ipd,'stiching_in_stage')
		cutting_attributes = get_attributes(item_list, item_name, cutting_out_stage, dept_attribute,ipd, process)
		receivables, total_qty  = get_receivables(cutting_attributes, process_cost, lot, uom, doc, supplier, ipd)
		deliverables  =  get_deliverables(bom, lot)

	else:		
		for item in ipd_doc.ipd_processes:
			if item.process_name == process:
				if ipd_doc.stiching_in_stage == item.stage:
					attributes = get_attributes(item_list, item_name, item.stage, dept_attribute, ipd)
					x = attributes.copy()
					x.update(bom)
					deliverables  = get_deliverables(x, lot)
					receivables, total_qty  = get_receivables(attributes, process_cost, lot, uom, doc, supplier, ipd)
				
				elif lot_doc.pack_in_stage == item.stage:
					deliverables = item_list.copy()
					receivables, total_qty  = get_receivables(deliverables, process_cost, lot, uom, doc, supplier, ipd)
					item_list.update(bom)
					deliverables = get_deliverables(item_list, lot)

				else:
					attributes = get_attributes(item_list, item_name, item.stage, dept_attribute)
					receivables, total_qty = get_receivables(attributes, process_cost, lot, uom, doc, supplier, ipd)
					attributes.update(bom)
					deliverables = get_deliverables(attributes, lot)
				break
	return deliverables, receivables, total_qty

def get_deliverables(items, lot):
    deliverables = []
    for item_name, variants in items.items():
        for variant, details in variants.items():
            deliverables.append({
				'item_variant': variant,
				'lot':lot,
				'qty':details['qty'],
				'uom':details['uom'],
				'table_index': details['table_index'],
				'row_index':str(details['table_index'])+""+str(details['row_index']),
				'pending_quantity':details['qty'],
				'is_calculated':True,
			})
    return deliverables

def get_receivables(items, process,lot, uom, doc, supplier, ipd, conversion_details = None, out_uom = None):
	receivables = []
	total_qty = 0
	for item_name,variants in items.items():
		for variant, details in variants.items():
			rate, cost_doc = get_rate_and_quantity(process,variant,details['qty'],doc, supplier)
			attr_qty = get_attributes_qty(ipd, process, cost_doc)
			rate = rate/attr_qty
			uom_factor = 1
			receivable_uom = uom
			if conversion_details:
				uom_factor = get_uom_conversion_factor(conversion_details, uom, out_uom)
				receivable_uom = out_uom
			qty = math.ceil(details['qty']*uom_factor)	
			total_qty += qty
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
	return receivables, total_qty	

def get_attributes_qty(ipd, process, process_cost_doc):
	depends_on_attr = frappe.get_value("Process Cost", process_cost_doc,"depends_on_attribute")
	if depends_on_attr:
		return 1
	
	ipd_doc = frappe.get_cached_doc("Item Production Detail",ipd)
	if ipd_doc.stiching_process == process or ipd_doc.packing_process == process:
		return 1
	elif ipd_doc.cutting_process == process:
		return len(ipd_doc.stiching_item_details)
	else:
		for procesess in ipd_doc.ipd_processes:
			if procesess.process_name == process:
				if procesess.stage == ipd_doc.pack_in_stage or procesess.stage == ipd_doc.pack_out_stage:
					return 1
				elif procesess.stage == ipd_doc.stiching_in_stage:
					return len((ipd_doc.stiching_item_details))
	return 1

def get_attributes(items, itemname, stage, dependent_attribute, ipd=None, process=None):
	item_list = {
		itemname: {}
	}
	ipd_doc = None
	if ipd:
		ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)

	for item_name,variants in items.items():
		item_attribute_details = get_attribute_details(item_name)
		for variant, details in variants.items():
			current_variant = frappe.get_cached_doc("Item Variant", variant)
			attributes = get_receivable_item_attribute_details(current_variant, item_attribute_details, stage)

			if item_attribute_details['dependent_attribute']:
				attributes[dependent_attribute] = stage
			itemname = current_variant.item
			if not ipd_doc:
				new_variant = get_or_create_variant(itemname, attributes)
				if not item_list.get(itemname):
					item_list[itemname] = {}
					
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
				set_item_stitching_attrs = {}
				if ipd_doc.is_set_item:
					part = None
					for attr in current_variant.attributes:
						if attr.attribute == ipd_doc.set_item_attribute:
							part = attr.attribute_value
							break

					for i in ipd_doc.stiching_item_details:
						set_item_stitching_attrs[i.stiching_attribute_value] = i.set_item_attribute_value

					for id,item in enumerate(ipd_doc.stiching_item_details):
						attributes[ipd_doc.stiching_attribute] = item.stiching_attribute_value
						v = True
						panel_part = set_item_stitching_attrs[item.stiching_attribute_value]
						if panel_part != part:
							v = False							
						if v:
							new_variant = get_or_create_variant(itemname, attributes)
							if item_list[itemname].get(new_variant):
								item_list[itemname][new_variant]['qty'] += (details['qty']*item.quantity)
							else:	
								item_list[itemname][new_variant] = {
									'qty': details['qty']*item.quantity,
									'process': details['process'],
									'uom':details['uom'],
									'table_index':details['table_index'],
									'row_index':str(details['table_index'])+""+str(details['row_index'])+""+str(id)
								}
				else:
					for id,item in enumerate(ipd_doc.stiching_item_details):
						attributes[ipd_doc.stiching_attribute] = item.stiching_attribute_value
						new_variant = get_or_create_variant(itemname, attributes)
						if item_list[itemname].get(new_variant):
							item_list[itemname][new_variant]['qty'] += (details['qty']*item.quantity)
						else:	
							item_list[itemname][new_variant] = {
								'qty': details['qty']*item.quantity,
								'process': details['process'],
								'uom':details['uom'],
								'table_index':details['table_index'],
								'row_index':str(details['table_index'])+""+str(details['row_index'])+""+str(id)
							}
							if process:
								item_list[itemname][new_variant]['attributes'] = attributes
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
				variant_name = get_or_create_variant(item['item'], attributes)
				item1['item_variant'] = variant_name
				item1['quantity'] = row['work_order_qty'][val]
				item1['row_index'] = id1
				item1['table_index'] = id1
				i = False
				for id3, value in enumerate(row['work_order_qty'].keys()):
					if row['work_order_qty'][value]:
						i = True
						break
				if i:
					item_list.append(item1)
		else:
			item1 = {}
			attributes = row['attributes']
			variant_name = item['item']
			variant_name = get_or_create_variant(item['item'], attributes)
			item1['item_variant'] = variant_name
			item1['quantity'] = row['work_order_qty']
			item1['table_index'] = id1
			item1['row_index'] = id1
			if item1['quantity']:
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
			"qty":item['quantity'],
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

@frappe.whitelist()
def add_comment(doc_name, date, reason):
	doc = frappe.get_doc('Work Order', doc_name)
	text = f"Delivery date changed from {doc.expected_delivery_date} to {date} <br> Reason: {reason}"
	doc.expected_delivery_date = date
	doc.add_comment('Comment',text=text)
	doc.save()
	
@frappe.whitelist()
def update_stock(work_order):
	res = get_variant_stock_details()
	sl_entries = []
	doc = frappe.get_doc("Work Order", work_order)
	for data in doc.deliverables:
		if data.qty - data.stock_update > 0 and res.get(data.item_variant):
			sl_entries.append({
				"item": data.item_variant,
				"warehouse": doc.supplier,
				"lot": doc.lot,
				"voucher_type": doc.doctype,
				"voucher_no": work_order,
				"voucher_detail_no": data.name,
				"qty": (data.qty - data.stock_update) * -1,
				"uom": data.uom,
				"rate": data.rate,
				"is_cancelled": 1 if data.docstatus == 2 else 0,
				"posting_date": nowdate(),
				"posting_time": nowtime(),
			})
			data.stock_update = data.qty
	make_sl_entries(sl_entries)
	doc.open_status = "Close"
	doc.is_delivered = True
	doc.total_quantity = 0
	doc.save()
