# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe
import copy
from frappe.model.document import Document 

from production_api.production_api.doctype.item_production_detail.item_production_detail import get_attribute_values as get_lot_attribute_values
from production_api.production_api.doctype.item.item import get_attribute_values as get_item_attribute_values, get_attributes

class ItemBOMAttributeMapping(Document):
	def validate(self):
		if self.flags.ignore_validate:
			return
		bom_attributes = list(set([i.attribute for i in self.bom_item_attributes]))
		bom_item_attributes = get_attributes(self.bom_item)
		if len(bom_attributes) != len(bom_item_attributes):
			frappe.throw("Please use all the BOM Item Attributes")
		flag = True
		for attr in bom_item_attributes:
			if attr not in bom_attributes:
				flag = False
				break
		if not flag:
			frappe.throw("Please use all the BOM Item Attributes")
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
				elif len(bom_attr_values) > 0:
					for value in item_attr_values:
						if not value in bom_attr_values:
							frappe.throw("Bom Item does not have all the attribute values as the Item.")
		
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
		if len(item_mapping_attributes) > 0 or len(bom_mapping_attributes) > 0:
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