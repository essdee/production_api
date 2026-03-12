# Copyright (c) 2026, Essdee and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import (
	fetch_combination_items, save_item_details,
)
from production_api.utils import update_if_string_instance


class CuttingOrder(Document):
	def autoname(self):
		self.naming_series = "CO-.YY..MM.-.{#####}."

	def onload(self):
		self.load_attribute_list()

		set_items = fetch_combination_items(self.get('set_item_combination_details'))
		if len(set_items['values']) > 0:
			self.set_onload('set_item_detail', set_items)

		stich_items = fetch_combination_items(self.get('stiching_item_combination_details'))
		if len(stich_items['values']) > 0:
			self.set_onload('stiching_item_detail', stich_items)

	def load_attribute_list(self):
		attribute_list = []
		for attribute in self.item_attributes:
			attribute_doc = frappe.get_cached_doc("Item Attribute", attribute.attribute)
			if not attribute_doc.numeric_values:
				if attribute.mapping != None:
					doc = frappe.get_cached_doc("Item Item Attribute Mapping", attribute.mapping)
					attribute_list.append({
						'name': attribute.name,
						'attr_name': attribute.attribute,
						'attr_values_link': attribute.mapping,
						'attr_values': doc.values,
						'doctype': 'Item Item Attribute Mapping'
					})
				else:
					attribute_list.append({
						'name': attribute.name,
						'attr_name': attribute.attribute,
						'attr_values_link': attribute.mapping,
						'attr_values': [],
						'doctype': 'Item Item Attribute Mapping'
					})
		self.set_onload('attr_list', attribute_list)

	def before_validate(self):
		if self.get('set_item_detail') and self.is_set_item:
			set_details = save_item_details(self.set_item_detail)
			self.set('set_item_combination_details', set_details)

		if self.get('stiching_item_detail'):
			stiching_detail = save_item_details(self.stiching_item_detail, ipd_doc=self)
			self.set('stiching_item_combination_details', stiching_detail)

		if not self.is_set_item:
			self.set('set_item_combination_details', [])
			self.set('major_attribute_value', None)
			self.set('set_item_attribute', None)

		if self.is_set_item and not self.is_new():
			mapping = None
			for item in self.item_attributes:
				if item.attribute == self.set_item_attribute:
					mapping = item.mapping
					break
			if mapping:
				map_doc = frappe.get_cached_doc("Item Item Attribute Mapping", mapping)
				map_values = [v.attribute_value for v in map_doc.values]

				check_dict = {}
				for attr in self.stiching_item_details:
					if attr.is_default:
						if check_dict.get(attr.set_item_attribute_value):
							frappe.throw(f"Select only one Is Default for {attr.set_item_attribute_value}")
						else:
							check_dict[attr.set_item_attribute_value] = 1

				if len(check_dict) < len(map_values):
					frappe.throw("Select Is default for all Set Item Attributes")

	def validate(self):
		# Delete orphaned mappings for removed attribute rows
		if not self.is_new():
			previous = self.get_doc_before_save()
			if previous:
				current_mappings = {a.mapping for a in self.get('item_attributes') if a.mapping}
				for attr in previous.get('item_attributes'):
					if attr.mapping and attr.mapping not in current_mappings:
						frappe.delete_doc("Item Item Attribute Mapping", attr.mapping, ignore_permissions=True)

		# Auto-create mappings for new attribute rows
		for attribute in self.get('item_attributes'):
			if not attribute.mapping:
				doc = frappe.new_doc("Item Item Attribute Mapping")
				doc.attribute_name = attribute.attribute
				doc.save()
				attribute.mapping = doc.name

		if not self.is_new():
			if self.packing_attribute:
				self.packing_tab_validations()

			if self.stiching_attribute and len(self.stiching_item_details) > 0:
				self.stiching_tab_validations()

	def packing_tab_validations(self):
		if self.packing_combo == 0:
			frappe.throw("The packing combo should not be zero")

		if self.packing_attribute_no == 0:
			frappe.throw("The packing attribute no should not be zero")

		mapping = None
		for item in self.item_attributes:
			if item.attribute == self.packing_attribute:
				mapping = item.mapping
				break

		if mapping:
			map_doc = frappe.get_cached_doc("Item Item Attribute Mapping", mapping)
			if len(map_doc.values) < self.packing_attribute_no:
				frappe.throw(f"The Packing attribute no is {self.packing_attribute_no} But there is only {len(map_doc.values)} attributes are available")

		if len(self.packing_attribute_details) != self.packing_attribute_no:
			frappe.throw(f"Only {self.packing_attribute_no} {self.packing_attribute}'s are required")

		sum_qty = 0.0
		attr = set()
		for row in self.packing_attribute_details:
			if not row.quantity:
				frappe.throw("Enter value in Packing Attribute Details, Zero is not considered as a valid quantity")
			sum_qty += row.quantity
			attr.add(row.attribute_value)

		if sum_qty < self.packing_combo or sum_qty > self.packing_combo:
			frappe.throw(f"In Packing Attribute Details, the sum of quantity should be {self.packing_combo}")

		if len(attr) != len(self.packing_attribute_details):
			frappe.throw("Duplicate Attribute values are occured in Packing Attribute Details")

	def stiching_tab_validations(self):
		if len(self.stiching_item_details) == 0:
			frappe.throw("Enter stiching attribute details")

		attr = set()
		for row in self.stiching_item_details:
			if not row.quantity:
				frappe.throw("Enter value in Stiching Item Details, Zero is not considered as a valid quantity")
			attr.add(row.stiching_attribute_value)

		if len(attr) != len(self.stiching_item_details):
			frappe.throw("Duplicate Attribute values are occured in Stiching Item Details")


@frappe.whitelist()
def update_attribute_mapping_values(mapping, values):
	if isinstance(values, str):
		values = json.loads(values)
	doc = frappe.get_doc("Item Item Attribute Mapping", mapping)
	doc.set("values", [])
	for v in values:
		doc.append("values", {"attribute_value": v})
	doc.save()


@frappe.whitelist()
def get_co_new_combination(attribute_mapping_value, packing_attribute_details, major_attribute_value, is_same_packing_attribute=False, doc_name=None):
	packing_attribute_details = update_if_string_instance(packing_attribute_details)
	if isinstance(packing_attribute_details, list):
		pass
	elif isinstance(packing_attribute_details, dict):
		packing_attribute_details = list(packing_attribute_details.values()) if packing_attribute_details else []

	doc = frappe.get_cached_doc('Item Item Attribute Mapping', attribute_mapping_value)
	attributes = [item.attribute_value for item in doc.values]

	stiching_item_details = {}
	set_item_details = {}
	is_default_list = []
	co_doc = None

	if doc_name:
		co_doc = frappe.get_doc("Cutting Order", doc_name)
		if co_doc.is_set_item:
			for item in co_doc.stiching_item_details:
				stiching_item_details[item.stiching_attribute_value] = item.set_item_attribute_value
				if item.is_default:
					is_default_list.append(item.stiching_attribute_value)

			for item in co_doc.set_item_combination_details:
				set_item_details.setdefault(item.major_attribute_value, {})
				set_item_details[item.major_attribute_value][item.set_item_attribute_value] = item.attribute_value

	if isinstance(is_same_packing_attribute, str):
		is_same_packing_attribute = is_same_packing_attribute in ('true', 'True', '1')

	item_detail = []
	for item in packing_attribute_details:
		item_list = {}
		item_list['major_attribute'] = item['attribute_value']
		item_list['val'] = {}
		for i in attributes:
			if i == major_attribute_value:
				item_list['val'][i] = item['attribute_value']
			elif is_same_packing_attribute:
				if doc_name and co_doc and co_doc.is_set_item:
					part = stiching_item_details[i]
					item_list['val'][i] = set_item_details[item['attribute_value']][part]
				else:
					item_list['val'][i] = item['attribute_value']
			elif doc_name and co_doc and co_doc.is_set_item and i in is_default_list:
				part = stiching_item_details[i]
				item_list['val'][i] = set_item_details[item['attribute_value']][part]
			else:
				item_list['val'][i] = None
		item_detail.append(item_list)

	item_details = {}
	item_details['attributes'] = attributes
	item_details['values'] = item_detail
	return item_details
