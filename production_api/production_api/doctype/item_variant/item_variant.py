# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ItemVariant(Document):
	def set_item(self):
		item = frappe.get_doc("Item", self.item)
		self.set_onload('__parent_item', item.as_dict())
	
	def autoname(self):
		self.name = self.get_name()
	
	def get_name(self):
		variant_name = self.item
		for attribute in self.attributes:
			if not attribute.display_name_is_empty:
				if not (attribute.display_name or attribute.attribute_value):
					frappe.throw("The set of attributes for this item is not correct")
				variant_name += '-' + (attribute.display_name or attribute.attribute_value)
		return variant_name
	
	def get_attribute_value(self, attribute):
		attribute_value = None
		for attr in self.attributes:
			if attr.attribute == attribute:
				attribute_value = attr.attribute_value
				break
		
		return attribute_value

	def rename_variant(self):
		name = self.get_name()
		print(self.name, name)
		if name != self.name:
			self.rename(name, force=True)



@frappe.whitelist()
def rename_item_variant(variant):
	variant = frappe.get_doc("Item Variant", variant)
	variant.rename_variant()
	return variant.name


def spine_set_item(payload):
	doc = payload.get("doc_to_publish")
	if not doc:
		return None
	if not isinstance(doc, Document):
		return payload
	doc.set("__onload", frappe._dict())
	doc.run_method("set_item")
	return payload

def on_doctype_update():
	frappe.db.add_index("Item Variant Attribute", ["attribute","attribute_value"])