# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ItemDependentAttributeMapping(Document):
	pass
	# def before_save(self):
	# 	x = 0
	# 	for items in self.details:
	# 		item = items.as_dict()
	# 		if item.is_final == 1:
	# 			x = x + 1
	# 		if x == 2:
	# 			frappe.throw("More than one final state for this item")	

				
				
def get_dependent_attribute_details(name):
	"""
	Sample output - 
		{
			"attribute": "Stage",
			"attr_list": {
				"pack": {
					"uom": "Box",
					"name": None,
					"attributes": ["Size"]
				}
			}
		}
	"""
	dependent_attribute = {}
	dependent_attribute_mapping = frappe.get_cached_doc("Item Dependent Attribute Mapping", name)
	dependent_attribute["attribute"] = dependent_attribute_mapping.dependent_attribute
	attr_list = {}
	for d in dependent_attribute_mapping.details:
		attr_list.setdefault(d.attribute_value, {}).setdefault("attributes", [])
		attr_list[d.attribute_value]["uom"] = d.uom
		attr_list[d.attribute_value]["name"] = d.display_name
		# attr_list[d.attribute_value]["is_final"] = d.is_final

	for d in dependent_attribute_mapping.mapping:
		attr_list.setdefault(d.dependent_attribute_value, {}).setdefault("attributes", [])
		attr_list[d.dependent_attribute_value]["attributes"].append(d.depending_attribute)
		attr_list[d.dependent_attribute_value].setdefault("uom", None)
		attr_list[d.dependent_attribute_value].setdefault("name", None)
		# attr_list[d.dependent_attribute_value].setdefault("is_final", 0)

	dependent_attribute["attr_list"] = attr_list
	return dependent_attribute