# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

from six import string_types
import json

import frappe
from frappe.model.document import Document
from production_api.production_api.doctype.item.item import create_variant, get_or_create_variant, rename_item
from production_api.production_api.doctype.item_dependent_attribute_mapping.item_dependent_attribute_mapping import get_dependent_attribute_details

class FGItemMaster(Document):
	def validate(self):
		if frappe.flags.in_patch:
			return
		sizes = [size.attribute_value for size in self.sizes]
		self.set("available_sizes", ",".join(sizes))
	
	# function that is used to sync the item with other systems
	def sync_item(self, rename=False):
		push_enabled = frappe.db.get_single_value("FG Settings", "enable_auto_update")
		if not push_enabled:
			return
		if rename:
			if self.item:
				sync_rename_item(self.item, self.name, brand=self.brand)
		else:
			create_or_update_item(self)

@frappe.whitelist()
def sync_fg_items(names, rename=False):
	if isinstance(names, string_types):
		names = json.loads(names)
	frappe.enqueue(method=sync_fg_item_background, fg_items=names, rename=rename)
	return "Queued Item for Sync"

def sync_fg_item_background(fg_items, rename=False):
	exceptions = {}
	for fg_item in fg_items:
		try:
			doc = frappe.get_doc("FG Item Master", fg_item)
			doc.sync_item(rename=rename)
		except Exception as exc:
			err_message = f"{str(exc)}\n{frappe.get_traceback(with_context=True)}"
			exceptions[fg_item] = err_message
	if len(exceptions) > 0:
		frappe.log_error("FG Item Master Sync Failed", message=json.dumps(exceptions))

def create_or_update_item(fg_item):
	if not fg_item.template:
		frappe.throw("Please set a template for the item")
	doc = None
	is_new = False
	if fg_item.item:
		doc = frappe.get_doc("Item", fg_item.item)
	else:
		is_new = True
		doc = create_item(fg_item)
		fg_item.item = doc.name
		fg_item.save()
	doc.update({
		"hsn_code": fg_item.hsn,
		"disabled": fg_item.disabled,
		"is_stock_item": 1,
		"is_purchase_item": 1,
		"is_sales_item": 1,
	})

	# Update Size
	sizes = [size.attribute_value for size in fg_item.sizes]
	mapping = None
	for attributes in doc.attributes:
		if attributes.attribute == "Size":
			mapping = attributes.mapping
			break
	if not mapping:
		frappe.throw("Please set a Size attribute for the item")
	mapping_doc = frappe.get_doc("Item Item Attribute Mapping", mapping)
	mapping_size = [size.attribute_value for size in mapping_doc.values]
	updated = False
	for size in sizes:
		if size not in mapping_size:
			updated = True
			mapping_doc.append("values", {
				"attribute_value": size,
			})
	if updated:
		mapping_doc.save()
	
	# Update Box conversion factor in UOM Conversion Details
	for uom_conversion in doc.uom_conversion_details:
		if uom_conversion.uom == "Box":
			uom_conversion.conversion_factor = fg_item.pcs_per_box
			break
	
	doc.save()
	# create size variants
	dependent_attribute_value = None
	if doc.dependent_attribute:
		dependent_attribute_details = get_dependent_attribute_details(doc.dependent_attribute_mapping)
		for attr, value in dependent_attribute_details["attr_list"].items():
			if value["attributes"] == ["Size"]:
				dependent_attribute_value = attr
				break
		if not dependent_attribute_value:
			frappe.throw("Please validate the template and set a Size attribute")
	for size in sizes:
		args = {
			"Size": size,
		}
		if dependent_attribute_value:
			args[doc.dependent_attribute] = dependent_attribute_value
		get_or_create_variant(doc.name, args)
	
	# if not is_new and (doc.brand != fg_item.brand or doc.name1 != fg_item.name):
	# 		rename_item(doc.name, fg_item.name, brand=fg_item.brand)

def sync_rename_item(item_name, brand, new_name):
	rename_item(item_name, new_name, brand=brand)

def create_item(fg_item):
	doc = frappe.new_doc("Item")
	fields = {
		"default_unit_of_measure": "default_unit_of_measure",
		"secondary_unit_of_measure": "secondary_unit_of_measure",
		"uom_conversion_details": "uom_conversion_details",
		"primary_attribute": "primary_attribute",
		"dependent_attribute": "dependent_attribute",
		"dependent_attribute_mapping": "dependent_attribute_mapping",
		"attributes": "attributes",
		"additional_parameters": "additional_parameters",
	}
	template = frappe.get_doc("FG Item Master Template", fg_item.template)
	for field, value in fields.items():
		doc.set(field, template.get(value))
	doc.update({
		"name1": fg_item.name,
		"brand": fg_item.brand,
	})
	doc.insert()
	return doc
