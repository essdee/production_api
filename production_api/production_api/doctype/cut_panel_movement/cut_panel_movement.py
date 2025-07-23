# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from itertools import groupby
from operator import itemgetter
from frappe.model.document import Document
from production_api.mrp_stock.utils import get_combine_datetime
from production_api.utils import update_if_string_instance, get_tuple_attributes
from production_api.mrp_stock.doctype.stock_entry.stock_entry import fetch_stock_entry_items
from production_api.production_api.doctype.item.item import get_or_create_variant, get_attribute_details
from production_api.production_api.doctype.purchase_order.purchase_order import get_item_attribute_details, get_item_group_index
from production_api.production_api.doctype.item_dependent_attribute_mapping.item_dependent_attribute_mapping import get_dependent_attribute_details

class CutPanelMovement(Document):
	def onload(self):
		if self.cut_panel_movement_json and len(self.cut_panel_movement_json) > 0:
			json_data = update_if_string_instance(self.cut_panel_movement_json)
			self.set_onload("movement_details", json_data)

	def before_cancel(self):
		if self.against_id:
			frappe.throw("Can't cancel this document")

	def before_validate(self):
		if self.docstatus == 1:
			return

		if self.is_new():
			res = frappe.db.sql(
				"""
					SELECT name FROM `tabCut Panel Movement` WHERE lot = %(lot)s 
					AND from_warehouse = %(from_location)s AND docstatus = 0
				""", {"lot": self.lot, "from_location": self.from_warehouse}, as_dict=True
			)
			if len(res) > 0:
				frappe.throw(f"Already a Cut Panel Movement was not Submitted for Supplier {self.from_warehouse} on Lot {self.lot}")
		
		if not self.is_new():
			if self.get('movement_data'):
				items = update_if_string_instance(self.movement_data)
				if items['accessory_data']:
					for item in items['accessory_data']:
						if not item['moved_weight']:
							item['moved_weight'] = 0
						if item['weight'] < item['moved_weight']:
							frappe.throw("Accessory Moving Weight Greater than Used Weight")
				items = get_total(items)
				self.set("cut_panel_movement_json", items)
	
	def before_submit(self):
		datas = {}
		json_data = update_if_string_instance(self.cut_panel_movement_json)
		panels = json_data['panels']
		is_set_item = json_data['is_set_item']
		data = json_data['data']
		for colour in data:
			datas[colour] = {"part":data[colour]['part'], 'data':[]}
			for row in data[colour]['data']:
				if row['bundle_moved']:
					datas[colour]['data'].append(row)
				else:
					if is_set_item:
						part = data[colour]['part']
						for panel in panels[part]:
							x = panel+"_moved"
							if panel in row and x in row and row[x] == True:
								datas[colour]['data'].append(row)
								break
					else:
						for panel in panels:
							x = panel+"_moved"
							if panel in row and x in row and row[x] == True:
								datas[colour]['data'].append(row)
								break
		json_data['data'] = datas
		accessory = json_data['accessory_data']
		if accessory:
			accessories = []
			for acc in accessory:
				if acc['moved_weight'] > 0:
					accessories.append(acc)
			json_data['accessory_data'] = accessories		

		self.set("cut_panel_movement_json", json_data)

	def on_submit(self):	
		if self.movement_from_cutting:
			update_accessory(self.cutting_plan, self.cut_panel_movement_json, 1)
	
	def on_cancel(self):
		if self.movement_from_cutting:
			update_accessory(self.cutting_plan, self.cut_panel_movement_json, 2)

def get_total(items):
	colour_panel = {}
	total_bundle = {}
	for colour in items["data"].keys():
		colour_panel[colour] = {}
		total_bundle[colour] = 0
		if items["is_set_item"]:
			pt = items["data"][colour]["part"]
			for i in range(len(items["data"][colour]["data"])):
				item = items["data"][colour]["data"][i]
				qty = 0

				for panel in items["panels"][pt]:
					if panel not in colour_panel[colour]:
						colour_panel[colour][panel] = 0
					
					if panel in item:
						if item.get(f"{panel}_moved"):
							qty += 1
							colour_panel[colour][panel] += item[panel]
				item["total"] = qty
				total_bundle[colour] += qty
				items["data"][colour]["data"][i] = item
		else:
			for i in range(len(items["data"][colour]["data"])):
				item = items["data"][colour]["data"][i]
				qty = 0

				for panel in items["panels"]:
					if panel not in colour_panel[colour]:
						colour_panel[colour][panel] = 0

					if panel in item:
						if item.get(f"{panel}_moved"):
							qty += 1
							colour_panel[colour][panel] += item[panel]
				item["total"] = qty
				total_bundle[colour] += qty
				items["data"][colour]["data"][i] = item
		items["total_pieces"] = colour_panel
		items['total_bundles'] = total_bundle
	return items

def update_accessory(cutting_plan, cut_panel_movement_json, docstatus):
	cut_panel_movement_json = update_if_string_instance(cut_panel_movement_json)
	if cut_panel_movement_json and cut_panel_movement_json['accessory_data']:
		accessory_data = cut_panel_movement_json['accessory_data']
		order = "ASC"
		if docstatus == 2:
			order = "DESC"

		cls_list = frappe.db.sql(
			f"""
				SELECT name FROM `tabCutting LaySheet` WHERE cutting_plan = '{cutting_plan}' ORDER BY lay_no {order}
			""", as_list = True
		)

		accessory = {}
		for row in accessory_data:
			key = (row['cloth_type'], row['colour'], row['shade'], row['dia'])
			accessory[key] = row['moved_weight']	
		
		for cls in cls_list:
			cls_doc = frappe.get_doc("Cutting LaySheet", cls)
			check = False
			for row in cls_doc.cutting_laysheet_accessory_details:
				key = (row.cloth_type, row.colour, row.shade, row.dia)
				if docstatus == 1:
					if key in accessory and row.moved_weight != row.weight and accessory[key] > 0:
						moved_weight = accessory[key]
						check = True
						balance_weight = row.weight - row.moved_weight
						if balance_weight >= moved_weight:
							row.moved_weight += moved_weight
							accessory[key] -= moved_weight
						else:
							row.moved_weight += balance_weight
							accessory[key] -= balance_weight
				else:
					if key in accessory and accessory[key] > 0 and row.moved_weight > 0:
						moved_weight = accessory[key]
						check = True
						if row.moved_weight >= moved_weight:
							row.moved_weight -= moved_weight
							accessory[key] -= moved_weight
						else:
							accessory[key] -= row.moved_weight
							row.moved_weight = 0
			if check:
				cls_doc.save()

@frappe.whitelist()
def get_cut_bundle_unmoved_data(from_location, lot, posting_date, posting_time, movement_from_cutting, cutting_plan=None, bundle_colour=None, get_collapsed=False):
	if cutting_plan:
		version = frappe.get_value("Cutting Plan", cutting_plan, "version")
		if version == "V1":
			frappe.throw("Can't create Cut Panel Movement for Version V1 Cutting Plan's")

	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values
	production_detail = frappe.get_value("Lot", lot, "production_detail")
	sizes = get_ipd_primary_values(production_detail)
	ipd_doc = frappe.get_doc("Item Production Detail", production_detail)
	panels = []
	if ipd_doc.is_set_item:
		panels = {}
		for row in ipd_doc.stiching_item_details:
			panels.setdefault(row.set_item_attribute_value, [])
	posting_datetime = get_combine_datetime(posting_date, posting_time)
	
	cb_list = frappe.db.sql("""
		SELECT cbml.name FROM `tabCut Bundle Movement Ledger` cbml
			INNER JOIN (
				SELECT cbm_key, MAX(posting_datetime) AS max_posting_datetime, lay_no FROM `tabCut Bundle Movement Ledger`
				WHERE posting_datetime <= %(datetime_value)s AND is_cancelled = 0 AND collapsed_bundle = 0
				AND is_collapsed = 0 AND transformed = 0 AND supplier = %(from_location)s  AND lot = %(lot)s
				GROUP BY cbm_key
			) latest_cbml
		ON cbml.cbm_key = latest_cbml.cbm_key AND cbml.posting_datetime = latest_cbml.max_posting_datetime
		WHERE cbml.is_cancelled = 0 AND cbml.posting_datetime <= %(datetime_value)s AND cbml.is_collapsed = 0 
		AND cbml.collapsed_bundle = 0 ORDER BY latest_cbml.lay_no asc
	""", {
		"datetime_value": posting_datetime,
		"from_location": from_location,
		"lot": lot,
	}, as_dict=True)

	lay_details = {}
	accessory_details = []
	accessories = {}

	for cb in cb_list:
		cb_doc = frappe.get_doc("Cut Bundle Movement Ledger", cb['name'])
		bundle_no = cb_doc.bundle_no
		parts = cb_doc.panel
		set_combination = update_if_string_instance(cb_doc.set_combination)
		major_colour = set_combination['major_colour']
		panel_colour = cb_doc.colour
		if ipd_doc.is_set_item:
			if set_combination.get('set_part'):
				if parts not in panels[set_combination['set_part']]:
					panels[set_combination['set_part']].append(parts)
				major_colour = "("+ major_colour +")" + set_combination["set_colour"] +"-"+set_combination.get('set_part')
			else:
				if parts not in panels[set_combination['major_part']]:
					panels[set_combination['major_part']].append(parts)
				major_colour = major_colour +"-"+set_combination.get('major_part')
		else:
			if parts not in panels:
				panels.append(parts)
		
		if bundle_colour:
			if major_colour != bundle_colour:
				continue

		comb = {
			"major_colour": set_combination.get("major_colour")
		}
		if set_combination.get("major_part"):
			comb['major_part'] = set_combination.get("major_part")
		sorted_key = tuple(sorted(comb.items()))
		lay_details.setdefault(cb_doc.lay_no, {})
		lay_details[cb_doc.lay_no].setdefault(major_colour, {})
		lay_details[cb_doc.lay_no][major_colour].setdefault(bundle_no, {})
		lay_details[cb_doc.lay_no][major_colour][bundle_no].setdefault(cb_doc.size, {})	
		lay_details[cb_doc.lay_no][major_colour][bundle_no][cb_doc.size].setdefault(cb_doc.shade, {})
		lay_details[cb_doc.lay_no][major_colour][bundle_no][cb_doc.size][cb_doc.shade].setdefault(sorted_key, {})
		lay_details[cb_doc.lay_no][major_colour][bundle_no][cb_doc.size][cb_doc.shade][sorted_key].setdefault(parts ,{
			"qty":0,
			"colour": panel_colour,
		})
		lay_details[cb_doc.lay_no][major_colour][bundle_no][cb_doc.size][cb_doc.shade][sorted_key][parts]["qty"] += cb_doc.quantity_after_transaction
	
	if movement_from_cutting:
		cls_docs = frappe.db.sql(
			"""
				SELECT name FROM `tabCutting LaySheet` WHERE cutting_plan = %(cutting_plan)s AND status = %(status)s
			""", {
				"cutting_plan": cutting_plan,
				"status": 'Label Printed',
			}, as_dict=True
		)
		for cls_doc in cls_docs:
			cls_doc = frappe.get_doc("Cutting LaySheet", cls_doc['name'])
			for row in cls_doc.cutting_laysheet_accessory_details:
				weight = row.weight - row.moved_weight
				if weight > 0:
					key = (row.cloth_item, row.cloth_type, row.colour, row.dia, row.shade)
					if key in accessories:
						accessories[key] += weight
					else:
						accessories[key] = weight

		for key, weight in accessories.items():
			cloth_item, cloth_type, colour, dia, shade = key
			accessory_details.append({
				"cloth_name":cloth_item,
				"cloth_type":cloth_type,
				"colour":colour,
				"shade":shade,
				"dia":dia,
				"weight": weight,
				"moved_weight": 0,
			}) 			

	final_data = {}
	for size in sizes:
		for lay_number, colour_dict in lay_details.items():
			if not lay_details.get(lay_number):
				continue
			for colour, colour_detail in colour_dict.items():
				for bundle_no in lay_details.get(lay_number).get(colour):
					for cur_size, panel_detail in lay_details.get(lay_number).get(colour).get(bundle_no).items():
						if cur_size == size:
							shade = list(panel_detail.keys())[0]
							d = {
								"part":None,
								"data":[]
							}
							if ipd_doc.is_set_item:
								splits = colour.split("-")
								d['part'] = splits[len(splits) - 1]

							final_data.setdefault(colour, d)

							for comb, panels_list in panel_detail[shade].items():
								duplicate = {}
								for panel in panels_list:
									duplicate['lay_no'] = lay_number
									duplicate['size'] = size
									duplicate['shade'] = shade
									duplicate['bundle_no'] = bundle_no
									duplicate[panel] = panel_detail[shade][comb][panel]['qty']
									duplicate[panel+"_colour"] = panel_detail[shade][comb][panel]["colour"]
									duplicate[panel+"_moved"] = False
								duplicate['set_combination'] = get_tuple_attributes(comb)
								duplicate['bundle_moved'] = False
								final_data[colour]["data"].append(duplicate)
	for colour in final_data:
		data = final_data[colour]["data"]
		final_data[colour]["data"] = sorted(data, key=itemgetter('size', 'shade', 'lay_no'))

	collapsed_bundles = []
	if get_collapsed:
		cbm_list = frappe.db.sql("""
			SELECT cbml.name FROM `tabCut Bundle Movement Ledger` cbml
				INNER JOIN (
					SELECT cbm_key, MAX(posting_datetime) AS max_posting_datetime, lay_no FROM `tabCut Bundle Movement Ledger`
					WHERE posting_datetime <= %(datetime_value)s AND is_cancelled = 0 AND collapsed_bundle = 1 AND transformed = 0 
					AND supplier = %(from_location)s AND colour = %(colour)s AND lot = %(lot)s GROUP BY cbm_key
				) latest_cbml
			ON cbml.cbm_key = latest_cbml.cbm_key AND cbml.posting_datetime = latest_cbml.max_posting_datetime
			WHERE cbml.posting_datetime <= %(datetime_value)s AND cbml.collapsed_bundle = 1
			ORDER BY latest_cbml.lay_no asc
		""", {
			"datetime_value": posting_datetime,
			"from_location": from_location,
			"lot": lot,
			"colour": bundle_colour,
		}, as_dict=True)

		for cbm in cbm_list:
			doc = frappe.get_doc("Cut Bundle Movement Ledger", cbm['name']) 
			collapsed_bundles.append({
				"moved": False,
				"size": doc.size,
				"colour": doc.colour,
				"panel": doc.panel,
				"quantity": doc.quantity_after_transaction,
				"shade": doc.shade,
				"lay_no": doc.lay_no,
				"bundle_no": doc.bundle_no,
				"set_combination": update_if_string_instance(doc.set_combination),
				"move_qty": 0,
			})
			
	return {
		"panels": panels,
		"data": final_data,
		"accessory_data": accessory_details,
		"is_set_item": ipd_doc.is_set_item,
		"collapsed_details": collapsed_bundles,
	}

@frappe.whitelist()
def create_stock_entry(doc_name):
	stock_entry_item_list, ipd = get_grouped_data(doc_name, "Stock Entry")
	data = fetch_stock_entry_items(stock_entry_item_list, ipd=ipd)
	return data

@frappe.whitelist()
def create_delivery_challan(doc_name, work_order):
	delivery_challan_item_list, ipd = get_grouped_data(doc_name, "Delivery Challan")
	doc = frappe.get_cached_doc("Work Order", work_order)
	items = []
	for item in doc.deliverables:
		item = item.as_dict()
		check = True
		for data in delivery_challan_item_list:
			set1 = update_if_string_instance(data['set_combination'])
			set2 = update_if_string_instance(item['set_combination'])
			if item['item_variant'] == data['item_variant'] and set1 == set2:
				check = False
				item['delivered_quantity'] = data['qty']
				items.append(item)
				break
		if check:
			item['delivered_quantity'] = 0
			items.append(item)	

	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	items = sorted(items, key = lambda i: i['row_index'])
	item_details = []
	for key, variants in groupby(items, lambda i: i['row_index']):
		variants = list(variants)
		current_variant = frappe.get_cached_doc("Item Variant", variants[0]['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		item = {
			'name': current_variant.item,
			'lot': variants[0]['lot'],
			'attributes': get_item_attribute_details(current_variant, current_item_attribute_details),
			'primary_attribute': current_item_attribute_details['primary_attribute'],
			"is_set_item": ipd_doc.is_set_item,
			"set_attr": ipd_doc.set_item_attribute,
			"pack_attr": ipd_doc.packing_attribute,
			"major_attr_value": ipd_doc.major_attribute_value,
			"item_keys": {},
			'values': {},
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'secondary_uom': variants[0]['secondary_uom'] or current_item_attribute_details['secondary_uom'],
			'comments': None,
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				set_combination = update_if_string_instance(variant['set_combination'])
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
							'set_combination':set_combination,
							'qty': variant['qty'],
							'delivered_quantity': variant['delivered_quantity'],
							'ref_docname': variant['name']
						}
						break
		else:
			item['values']['default'] = {
				'rate': variants[0]['rate'],
				"ref_doctype":"Work Order Deliverables",
				"is_calculated":variants[0].is_calculated,
				'qty': variants[0]['qty'],
				'delivered_quantity': variants[0]['delivered_quantity'],
				'ref_docname': variants[0]['name']
			}
		index = get_item_group_index(item_details, current_item_attribute_details)
		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				"lot":doc.lot,
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details["primary_attribute_values"],
				'dependent_attribute': current_item_attribute_details['dependent_attribute'],
				'items': [item]
			})
		else:
			item_details[index]['items'].append(item)
	return {
		"item_details": item_details,
		"supplier": doc.supplier,
		"supplier_name": doc.supplier_name,
		"supplier_address": doc.supplier_address,
		"supplier_address_details": doc.supplier_address_details,
	}

@frappe.whitelist()
def create_goods_received_note(doc_name, work_order, return_items=False):
	grn_item_list, ipd = get_grouped_data(doc_name, "Goods Received Note")
	doc = frappe.get_cached_doc("Work Order", work_order)
	items = []
	check_one_panel = True
	for item in doc.receivables:
		item = item.as_dict()
		check = True
		item['quantity'] = item['qty']
		for data in grn_item_list:
			set1 = update_if_string_instance(data['set_combination'])
			set2 = update_if_string_instance(item['set_combination'])
			if item['item_variant'] == data['item_variant'] and set1 == set2:
				check = False
				check_one_panel = False
				item['delivered_quantity'] = data['qty']
				items.append(item)
				break
		if check:
			items.append(item)
	if check_one_panel:
		frappe.throw("No Items for this Work Order")

	if return_items:
		return items
			
	lot = doc.lot
	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
	item_details = []
	default_received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
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
			'types':[],
			'default_uom': variants[0]['uom'] or current_item_attribute_details['default_uom'],
			'secondary_uom': variants[0]['secondary_uom'] or current_item_attribute_details['secondary_uom'],
			'comments': variants[0]['comments'],
		}
		if item['primary_attribute']:
			for attr in current_item_attribute_details['primary_attribute_values']:
				item['values'][attr] = {'qty': 0, 'rate': 0, "types": {}}
			for variant in variants:
				current_variant = frappe.get_cached_doc("Item Variant", variant['item_variant'])
				set_combination = update_if_string_instance(variant.get('set_combination', {}))
				if set_combination:
					if set_combination.get("major_part"):
						item['item_keys']['major_part'] = set_combination.get("major_part")
					if set_combination.get("major_colour"):
						item['item_keys']['major_colour'] = set_combination.get("major_colour")		

				for attr in current_variant.attributes:
					if attr.attribute == item.get('primary_attribute'):
						variant['received_types'] = {
							default_received_type: round(variant['qty'], 3)
						}
						item['values'][attr.attribute_value] = {
							'primary_attr': attr.attribute_value,
							'secondary_uom':variant['secondary_uom'],
							'secondary_qty': variant['secondary_qty'],
							'rate': variant.get('rate', 0),
							'tax': variant.get('tax', 0),
							'types': variant['received_types'] if variant.get('received_types') else {},
							'secondary_qty_json': variant['secondary_qty_json'] if variant.get('secondary_qty_json') else {},
							'set_combination': variant.get('set_combination', {})
						}
						item['values'][attr.attribute_value]['qty'] = 0
						item['values'][attr.attribute_value]['received'] = round(variant['qty'], 3)
						item['types'] = [default_received_type]
						item['values'][attr.attribute_value]['ref_doctype'] = "Work Order Receivables"
						item['values'][attr.attribute_value]['ref_docname'] = variant['name']
						break
		index = -1
		if item_details:
			index = get_item_group_index(item_details, current_item_attribute_details)

		if index == -1:
			item_details.append({
				'attributes': current_item_attribute_details['attributes'],
				"lot":lot,
				'primary_attribute': current_item_attribute_details['primary_attribute'],
				'primary_attribute_values': current_item_attribute_details['primary_attribute_values'],
				'dependent_attribute': current_item_attribute_details['dependent_attribute'],
				"dependent_attribute_details": current_item_attribute_details['dependent_attribute_details'],
				"is_set_item": ipd_doc.is_set_item,
				"set_attr": ipd_doc.set_item_attribute,
				"pack_attr": ipd_doc.packing_attribute,
				"major_attr_value": ipd_doc.major_attribute_value,
				'items': [item],
				"types": item['types'],
			})
		else:
			item_details[index]['items'].append(item)	
			
	for item in item_details:
		for row_item in item['items']:
			total_json = {}
			for key in row_item['values']:
				types_json = update_if_string_instance(row_item['values'][key]["types"])
				for type in row_item['types']:
					if types_json.get(type):
						total_json.setdefault(type, 0)
						total_json[type] += types_json.get(type)
			row_item['total_qty'] = total_json

	return {
		"item_details": item_details,
		"supplier": doc.supplier,
		"supplier_name": doc.supplier_name,
		"supplier_address": doc.supplier_address,
		"supplier_address_details": doc.supplier_address_details,
		"delivery_location": doc.delivery_location,
		"delivery_location_name": doc.delivery_location_name,
		"delivery_address": doc.delivery_address,
		"delivery_address_details": doc.delivery_address_details,
	}

def get_grouped_data(doc_name, doctype):
	doc = frappe.get_doc("Cut Panel Movement", doc_name)
	ipd, item_name = frappe.get_value("Lot", doc.lot, ["production_detail", "item"])
	ipd_doc = frappe.get_doc("Item Production Detail", ipd)
	panel_qty_dict = {}
	for item in ipd_doc.stiching_item_details:
		panel_qty_dict[item.stiching_attribute_value] = item.quantity
	cpm_json = update_if_string_instance(doc.cut_panel_movement_json)
	stock_entry_dict = {}
	group_dict = {}
	attr_details = get_dependent_attribute_details(ipd_doc.dependent_attribute_mapping)
	uom = attr_details['attr_list'][ipd_doc.stiching_in_stage]['uom']
	for colour in cpm_json['data']:
		if ipd_doc.is_set_item:
			part = cpm_json['data'][colour]['part']
			panels = cpm_json['panels'][part]
		else:
			panels = cpm_json['panels']

		for data in cpm_json['data'][colour]['data']:
			for grp_panel in panels:
				if data.get(grp_panel) and data[grp_panel+"_moved"]:
					panel_list = grp_panel.split(",")
					for panel in panel_list:	
						panel = panel.strip()
						grp_key = (panel, colour)
						if grp_key not in group_dict:
							group_dict[grp_key] = []
						key = {
							ipd_doc.primary_item_attribute: data['size'],
							ipd_doc.packing_attribute: data[grp_panel+'_colour'],
							ipd_doc.dependent_attribute: ipd_doc.stiching_in_stage,
							ipd_doc.stiching_attribute: panel,
							"set_combination": tuple(sorted(data['set_combination'].items())),
						}
						key = tuple(sorted(key.items()))
						panel_qty = data[grp_panel] * panel_qty_dict[panel]
						if key in stock_entry_dict:
							stock_entry_dict[key]["qty"] += panel_qty
						else:
							stock_entry_dict[key] = { "qty": panel_qty, "group_key": grp_key }

	for attrs_tuple in stock_entry_dict:
		attrs = get_tuple_attributes(attrs_tuple)
		qty = stock_entry_dict[attrs_tuple]['qty']
		grp_key = stock_entry_dict[attrs_tuple]['group_key']
		set_combination = get_tuple_attributes(attrs['set_combination'])
		del attrs['set_combination']
		variant = get_or_create_variant(item_name, attrs)
		group_dict[grp_key].append( {"item_variant": variant, "qty": qty, "set_combination": set_combination })
	
	table_index = -1
	row_index = -1
	item_list = []
	received_type = frappe.db.get_single_value("Stock Settings", "default_received_type")
	for (panel, colour), items in group_dict.items():
		sorted_items = sorted(items, key=lambda x: x['item_variant'])
		table_index += 1
		row_index += 1
		for item in sorted_items:
			if doctype == 'Stock Entry':
				item_list.append({
					"item": item['item_variant'],
					"qty": item['qty'],
					"lot": doc.lot,
					"received_type": received_type,
					"uom": uom,
					'table_index': table_index,
					'row_index': row_index,
					'set_combination': item['set_combination'],
				})
			else:
				item_list.append({
					"item_variant": item['item_variant'],
					"lot": doc.lot,
					"qty": item['qty'],
					'set_combination': item['set_combination'],
					"uom": uom,
					'table_index': table_index,
					'row_index': row_index,
				})
	table_index += 1
	row_index += 1
	for acc in cpm_json['accessory_data']:
		variant = get_or_create_variant(acc['cloth_name'], { ipd_doc.packing_attribute: acc['colour'], "Dia": acc['dia'] })
		uom = frappe.get_value("Item", acc['cloth_name'], "default_unit_of_measure")
		if doctype == 'Stock Entry':
			item_list.append({
				"item": variant,
				"qty": acc['moved_weight'],
				"lot": doc.lot,
				"received_type": received_type,
				"uom": uom,
				'table_index': table_index,
				'row_index': row_index,
				'set_combination': {},
			})
		else:
			item_list.append({
				"item_variant": variant,
				"lot": doc.lot,
				"qty": acc['moved_weight'],
				'set_combination': {},
				"uom": uom,
				'table_index': table_index,
				'row_index': row_index,
			})
		row_index += 1
	return item_list, ipd 
