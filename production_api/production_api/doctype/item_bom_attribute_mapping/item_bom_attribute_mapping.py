# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe, json
import copy
from six import string_types
from frappe.model.document import Document 
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_set_tri_struct, get_set_tri_combination, pop_attributes, get_comb_items, change_attr_list, get_combination_attr_list
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_attribute_values as get_lot_attribute_values
from production_api.production_api.doctype.item.item import get_attribute_values as get_item_attribute_values, get_attributes

class ItemBOMAttributeMapping(Document):
	def validate(self):
		if self.flags.ignore_validate:
			return
		bom_attributes = list(set([i.attribute for i in self.bom_item_attributes]))
		bom_item_attributes = get_attributes(self.bom_item)
		# if len(bom_attributes) != len(bom_item_attributes):
		# 	frappe.throw("Please use all the BOM Item Attributes")
		# flag = True
		# for attr in bom_item_attributes:
		# 	if attr not in bom_attributes:
		# 		flag = False
		# 		break
		# if not flag:
		# 	frappe.throw("Please use all the BOM Item Attributes")
		same_item_attributes = [i.attribute for i in self.item_attributes if i.same_attribute]
		same_attributes = [i.attribute for i in self.bom_item_attributes if i.same_attribute and i.attribute in same_item_attributes]
		item_mapping_attributes = [i.attribute for i in self.item_attributes if not i.attribute in same_attributes]
		bom_mapping_attributes = [i.attribute for i in self.bom_item_attributes if not i.attribute in same_attributes]
		if same_attributes and len(same_attributes) > 0:
			item_attributes = get_lot_attribute_values(self.item_production_detail, same_attributes)
			bom_item_attributes = get_item_attribute_values(self.bom_item, same_attributes)
			for attr in same_attributes:
				item_attr_values = item_attributes.get(attr)
				if not item_attr_values or len(item_attr_values) == 0:
					frappe.throw("Please specify attribute values for "+attr)
				bom_attr_values = bom_item_attributes.get(attr)
				if not bom_attr_values:
					frappe.throw("Bom Item does not have attribute "+attr)
				# elif len(bom_attr_values) > 0:
				# 	for value in item_attr_values:
				# 		if not value in bom_attr_values:
				# 			frappe.throw("Bom Item does not have all the attribute values as the Item.")
		
		first_row = [i for i in self.values if i.index == 0]
		for r in first_row:
			if r.type == 'item':
				if r.attribute in item_mapping_attributes:
					item_mapping_attributes.remove(r.attribute)
				else:
					frappe.throw(f"All Attribute values are not specified {r.attribute}")
			elif r.type == 'bom':
				if r.attribute in bom_mapping_attributes:
					bom_mapping_attributes.remove(r.attribute)
				else:
					frappe.throw("All Attribute values are not specified")

	def get_attribute_mapping(self):
		attribute_mapping_list = []
		values = sorted(self.values, key=lambda d: d.index)
		for v in values:
			if not len(attribute_mapping_list) > v.index:
				attribute_mapping_list.append({'item': {}, 'bom': {}})
			attribute_mapping_list[v.index][v.type][v.attribute] = v.attribute_value
		same_item_attributes = [i.attribute for i in self.item_attributes if i.same_attribute]
		same_attributes = [i.attribute for i in self.bom_item_attributes if i.same_attribute and i.attribute in same_item_attributes]
		if same_attributes and len(same_attributes) > 0:
			item_attributes = get_lot_attribute_values(self.item_production_detail, same_attributes)
			for attr in same_attributes:
				l1 = []
				attr_values = item_attributes[attr]
				for value in attr_values:
					for l in attribute_mapping_list:
						i = copy.deepcopy(l)
						i['item'][attr] = value
						i['bom'][attr] = value
						l1.append(i)
					if len(attribute_mapping_list) == 0:
						l1.append({
							"item": {attr: value},
							"bom": {attr: value},
						})
				attribute_mapping_list = copy.deepcopy(l1)
		return attribute_mapping_list
	
@frappe.whitelist()
def get_item_bom_mapping_combination(item_attributes, bom_attributes, attribute_values, ipd):
	if isinstance(item_attributes, string_types):
		item_attributes = json.loads(item_attributes)
	if isinstance(bom_attributes, string_types):
		bom_attributes = json.loads(bom_attributes)
	if isinstance(attribute_values, string_types):
		attribute_values = json.loads(attribute_values)
	
	# is_set_item = frappe.get_value("Item Production Detail", ipd, "is_set_item")
	from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_combination
	data = get_combination(ipd, item_attributes, "Cutting")
	items = []
	for row in data['items']:
		d = {}
		for attr in item_attributes:
			attr_key = get_attribute_name("item", attr)
			d[attr_key] = row[attr]

		for attr in bom_attributes:
			attr_key = get_attribute_name("bom", attr)
			d[attr_key] = None
		d['quantity'] = 0	
		d['included'] = True
		items.append(d)
	# check = True
	# if is_set_item and len(item_attributes) > 1:
	# 	data = get_comb(ipd, item_attributes, bom_attributes, attribute_values)
	# 	check = False

	# if check:
	# 	data = get_combination(item_attributes, bom_attributes, attribute_values)
	# for d in data:
	# 	d['quantity'] = 0
	return items

def get_attribute_name(type, attribute):
	return type+"_"+attribute

# def get_comb(ipd, attributes, bom_attributes, attribute_values):
# 	ipd_doc = frappe.get_cached_doc("Item Production Detail", ipd)
# 	if isinstance(attributes, string_types):
# 		attributes = json.loads(attributes)
# 	item_attributes = ipd_doc.item_attributes
# 	packing_attr = ipd_doc.packing_attribute
# 	packing_attr_details = ipd_doc.packing_attribute_details
	
# 	if isinstance(item_attributes, string_types):
# 		item_attributes = json.loads(item_attributes)
# 	if isinstance(packing_attr_details, string_types):
# 		packing_attr_details = json.loads(packing_attr_details)
	
# 	cloth_colours = []
# 	for pack_attr in packing_attr_details:
# 		cloth_colours.append(pack_attr.attribute_value)
	
# 	if ipd_doc.is_set_item:
# 		for row in ipd_doc.set_item_combination_details:
# 			if row.attribute_value not in cloth_colours:
# 				cloth_colours.append(row.attribute_value)

# 	item_attr_val_list = get_combination_attr_list(attributes,packing_attr, cloth_colours, item_attributes)

# 	stich_attr = ipd_doc.stiching_attribute
# 	set_attr = ipd_doc.set_item_attribute
# 	pack_attr = ipd_doc.packing_attribute
	
# 	item_list = []
# 	combination_type=""
# 	part_accessory_combination = {}

# 	if pack_attr in attributes and set_attr in attributes and stich_attr in attributes:
# 		x = item_attr_val_list.copy()
# 		del x[pack_attr]
# 		del x[stich_attr]

# 		set_data = {set_attr : {}}
# 		for i in item_attr_val_list[set_attr]:
# 			set_data[set_attr][i] = {
# 				pack_attr : [],
# 				stich_attr : []
# 			}

# 		x[set_attr] = set_data[set_attr]
# 		item_attr_list = x		
# 		item_attr_list = get_set_tri_struct(ipd_doc, item_attr_list, set_attr, pack_attr, stich_attr)
		
# 		set_attr_values = item_attr_list[set_attr]
# 		del item_attr_list[set_attr]
		
# 		attributes = pop_attributes(attributes, [set_attr, pack_attr, stich_attr])

# 		item_attr_val_list = item_attr_list
# 		item_list = get_set_tri_combination(set_attr_values, set_attr, pack_attr, stich_attr, combination_type, part_accessory_combination)

# 		attributes.append(set_attr)
# 		attributes.append(pack_attr)
# 		attributes.append(stich_attr)

# 	elif pack_attr in attributes and set_attr in attributes and stich_attr not in attributes:
# 		x = item_attr_val_list.copy()
# 		del x[pack_attr]
		
# 		set_data = {set_attr : {}}
# 		for i in item_attr_val_list[set_attr]:
# 			set_data[set_attr][i] = []

# 		x[set_attr] = set_data[set_attr]

# 		item_attr_list = x	
# 		for i in ipd_doc.set_item_combination_details:
# 			if i.attribute_value not in item_attr_list[set_attr][i.set_item_attribute_value]:
# 				item_attr_list[set_attr][i.set_item_attribute_value].append(i.attribute_value) 

# 		set_attr_values = item_attr_list[set_attr]
# 		del item_attr_list[set_attr]

# 		attributes = pop_attributes(attributes, [set_attr, pack_attr])
		
# 		item_attr_val_list = item_attr_list
# 		item_list = get_comb_items(set_attr_values, set_attr, pack_attr, combination_type, part_accessory_combination)
# 		attributes.append(set_attr)
# 		attributes.append(pack_attr)

# 	elif stich_attr in attributes and set_attr in attributes and pack_attr not in attributes:
# 		item_attr_list = change_attr_list(item_attr_val_list,ipd_doc.stiching_item_details,stich_attr,set_attr)
# 		set_attr_values = item_attr_list[set_attr]
# 		del item_attr_list[set_attr]
		
# 		attributes = pop_attributes(attributes, [set_attr, stich_attr])
# 		item_attr_val_list = item_attr_list
# 		item_list = get_comb_items(set_attr_values, set_attr, stich_attr, combination_type, part_accessory_combination)
# 		attributes.append(set_attr)
# 		attributes.append(stich_attr)
# 	else:
# 		data = get_combination(attributes, bom_attributes, attribute_values)
# 		return data

# 	items = []
# 	for item in item_list:
# 		d = {}
# 		for key, val in item.items():
# 			name = get_attribute_name('item', key)
# 			d[name] = val
# 		items.append(d)
# 	return items	

# def get_combination(item_attributes, bom_attributes, attribute_values):
# 	data = []
# 	attr = item_attributes[0]
# 	attr_values = attribute_values[attr]
# 	for attr_value in attr_values:
# 		d = {}
# 		attr_name = get_attribute_name('item', attr)
# 		d[attr_name] = attr_value
# 		data.append(d)

# 	if len(item_attributes) > 1:
# 		data1 = data.copy()
# 		data = []
# 		for idx, item in enumerate(item_attributes):
# 			if idx > 0:
# 				attr = item_attributes[idx]
# 				attr_values = attribute_values[attr]
# 				for attr_val in attr_values:
# 					for k in data1:
# 						d = k.copy()
# 						d[get_attribute_name('item', attr)] = attr_val
# 						data.append(d)
# 	for d in data:
# 		for bom_attr in bom_attributes:
# 			d[get_attribute_name('bom', bom_attr)] = None
	
# 	for d in data:
# 		d['included'] = True	
	
# 	return data
