# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cstr, flt
from six import string_types
import json
from frappe.model.document import Document
from frappe.desk.search import search_widget
from production_api.production_api.doctype.item_price.item_price import get_all_active_price


class Item(Document):

	def autoname(self):
		self.name1 = self.name1.strip()
		self.name = self.get_name(self.brand, self.name1)

	def get_name(self, brand, name):
		name = name.strip()
		if brand:
			name1 = name.split(' ')
			return name if name1[0].lower() == brand.lower() else brand + ' ' + name
		return name
	
	def after_rename(self, old, new, merge):
		variants = frappe.get_list('Item Variant', filters={"item": self.name}, pluck="name")
		for v in variants:
			doc = frappe.get_doc('Item Variant', v)
			newname = doc.get_name()
			if v != newname:
				doc.rename(name=newname, force=True)
	
	def load_attribute_list(self):
		"""Load Attribute List into `__onload`"""
		
		attribute_list = []
		for attribute in self.attributes:
			attribute_doc = frappe.get_doc("Item Attribute", attribute.attribute)
			if not attribute_doc.numeric_values:
				if attribute.mapping != None:
					doc = frappe.get_doc("Item Item Attribute Mapping", attribute.mapping)
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
	
	def load_bom_attribute_list(self):
		"""Load BOM Item Attribute Mapping List into `__onload`"""

		bom_attribute_list = []
		for bom in self.bom:
			if bom.attribute_mapping != None:
				doc = frappe.get_doc("Item BOM Attribute Mapping", bom.attribute_mapping)
				bom_attribute_list.append({
					'bom_item': bom.item,
					'bom_attr_mapping_link': bom.attribute_mapping,
					'bom_attr_mapping_based_on': bom.attribute_mapping_based_on,
					'bom_attr_mapping_list': doc.values,
					'doctype': 'Item BOM Attribute Mapping'
				})
		self.set_onload('bom_attr_list', bom_attribute_list)
	
	def load_price(self):
		"""Load Item Price List into `__onload`"""

		item_price_list = get_all_active_price(item = self.name)
		item_prices = []
		for price in item_price_list:
			doc = frappe.get_doc("Item Price", price.name)
			item_prices.append(doc)
		self.set_onload('item_price_list', item_prices)

	def onload(self):
		"""Load Attribute List and BOM Item Attribute Mapping List into `__onload`"""

		self.load_attribute_list()
		self.load_bom_attribute_list()
		self.load_price()

	def validate(self):
		"""Add a empty Mapping Table for each attribute"""
		if self.primary_attribute and self.primary_attribute not in [attribute.attribute for attribute in self.attributes]:
			frappe.throw("Default Attribute must be in Attribute List")
		
		if self.get('__islocal'):
			for attribute in self.get('attributes'):
				if attribute.mapping:
					doc = frappe.get_doc("Item Item Attribute Mapping", attribute.mapping)
					duplicate_doc = frappe.new_doc("Item Item Attribute Mapping")
			
					duplicate_doc.values = doc.values
					duplicate_doc.attribute_name= attribute.attribute 
					duplicate_doc.save()
					attribute.mapping = duplicate_doc.name
			
			for bom in self.get('bom'):
				if bom.attribute_mapping_based_on and bom.attribute_mapping:
					doc = frappe.get_doc("Item BOM Attribute Mapping", bom.attribute_mapping)
					duplicate_doc = frappe.new_doc("Item BOM Attribute Mapping")
					duplicate_doc.values = doc.values
					duplicate_doc.save()
					bom.attribute_mapping = duplicate_doc.name
		
		for attribute in self.get('attributes'):
			if attribute.mapping == None:
				doc = frappe.new_doc("Item Item Attribute Mapping")
				doc.attribute_name= attribute.attribute 
				doc.save()
				attribute.mapping = doc.name
		
		for bom in self.get('bom'):
			if bom.attribute_mapping_based_on and not bom.attribute_mapping:
				doc = frappe.new_doc("Item BOM Attribute Mapping")
				doc.save()
				bom.attribute_mapping = doc.name


@frappe.whitelist()
def get_attribute_details(item_name):
	"""Return Attribute Details of an item"""

	item = frappe.get_doc("Item", item_name)
	attributes = [attribute.attribute for attribute in item.attributes]
	primary_attribute_details = []
	if item.primary_attribute:
		attributes.remove(item.primary_attribute)
		for attribute in item.attributes:
			if attribute.attribute == item.primary_attribute:
				doc = frappe.get_doc("Item Item Attribute Mapping", attribute.mapping)
				primary_attribute_details = [value.attribute_value for value in doc.values]
	additional_parameters = [{'additional_parameter_key': a.additional_parameter_key, 'additional_parameter_value': a.additional_parameter_value} for a in item.additional_parameters]
	return {
		"item": item_name,
		"primary_attribute": item.primary_attribute,
		"attributes": attributes,
		"primary_attribute_values": primary_attribute_details,
		"default_uom": item.default_unit_of_measure,
		"secondary_uom": item.secondary_unit_of_measure,
		"additional_parameters": additional_parameters,
	}

@frappe.whitelist()
def get_complete_item_details(item_name):
	""" Return Item with it item mapping values """

	item = frappe.get_doc("Item", item_name)
	item = item.as_dict()
	from frappe.model import default_fields
	for attribute in item['attributes']:
		for fieldname in default_fields:
			if fieldname in attribute:
				del attribute[fieldname]

	for bom in item['bom']:
		for fieldname in default_fields:
			if fieldname in bom:
				del bom[fieldname]
	
	return item

def get_or_create_variant(template, args):
	variant_name = get_variant(template, args)
	if not variant_name:
		variant = create_variant(template, args)
		variant.insert()
		variant_name = variant.name
	return variant_name

def create_variant(template, args):
	if isinstance(args, string_types):
		args = json.loads(args)

	template = frappe.get_doc("Item", template)
	variant = frappe.new_doc("Item Variant")
	variant.item = template.name
	variant_attributes = []

	for d in template.attributes:
		if not args.get(d.attribute):
			frappe.throw("Please mention {0} attribute in {1}".format(d.attribute, template.name))
		variant_attributes.append({
			"attribute": d.attribute,
			"attribute_value": args.get(d.attribute)
		})

	variant.set("attributes", variant_attributes)

	return variant

def get_variant(template, args):
	"""
		Get variant of Item

		template: Item name
		args: A dictionary with "Attribute" as key and "Attribute Value" as value
	"""

	item_template = frappe.get_doc("Item", template)

	if isinstance(args, string_types):
		args = json.loads(args)
	if not args and item_template.attributes:
		frappe.throw("Please specify at least one attribute in the Attributes table")
	return find_variant(template, args)

def find_variant(template, args):
	
	possible_variants = get_variants_by_attributes(args, template)

	for variant in possible_variants:
		variant = frappe.get_doc("Item Variant", variant)

		if len(args.keys()) == len(variant.get("attributes")):
			# has the same number of attributes and values
			# assuming no duplication as per the validation in Item
			match_count = 0

			for attribute, value in args.items():
				for row in variant.attributes:
					if row.attribute==attribute and row.attribute_value== cstr(value):
						# this row matches
						match_count += 1
						break

			if match_count == len(args.keys()):
				return variant.name

def get_variants_by_attributes(args, template=None):
	items = []

	for attribute, values in args.items():
		attribute_values = values

		if not isinstance(attribute_values, list):
			attribute_values = [attribute_values]

		if not attribute_values: continue

		wheres = []
		query_values = []
		for attribute_value in attribute_values:
			wheres.append('( attribute = %s and attribute_value = %s )')
			query_values += [attribute, attribute_value]

		attribute_query = ' or '.join(wheres)

		if template:
			variant_of_query = 'AND t2.item = %s'
			query_values.append(template)
		else:
			variant_of_query = ''

		query = '''
			SELECT
				t1.parent
			FROM
				`tabItem Variant Attribute` t1
			WHERE
				1 = 1
				AND (
					{attribute_query}
				)
				AND EXISTS (
					SELECT
						1
					FROM
						`tabItem Variant` t2
					WHERE
						t2.name = t1.parent
						{variant_of_query}
				)
			GROUP BY
				t1.parent
			ORDER BY
				NULL
		'''.format(attribute_query=attribute_query, variant_of_query=variant_of_query)

		item_codes = set([r[0] for r in frappe.db.sql(query, query_values)])
		items.append(item_codes)

	if not args:
		attribute_query = ' item = %s '
		query_values = [template]
		query = '''
			SELECT 
				name
			FROM
				`tabItem Variant`
			WHERE
				1 = 1
				AND (
					{attribute_query}
				)
		'''.format(attribute_query=attribute_query)

		item_codes = set([r[0] for r in frappe.db.sql(query, query_values)])
		items.append(item_codes)

	res = list(set.intersection(*items))

	return res
def mapping_missing_attribute():
	doc=frappe.db.get_list("Item")
	for item in doc:
		value=frappe.get_doc("Item",item.name)
		no_of_attribute=len(value.attributes)
		for i in range(no_of_attribute):
			attribute=frappe.get_doc("Item Item Attribute Mapping",(value.attributes[i].mapping))
			if(attribute.attribute_name==None):
				attribute.attribute_name=value.attributes[i].attribute
				attribute.save()
				value.save()

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_item_attribute_values(doctype, txt, searchfield, start, page_len, filters):
	if (doctype != 'Item Attribute Value' or filters['item'] == None or filters['attribute'] == None):
		return []

	item_name = filters['item']
	attribute = filters['attribute']

	attr = frappe.get_doc("Item Attribute", attribute)
	if attr.numeric_values:
		search_widget(doctype=doctype, txt=txt, page_length=page_len, searchfield=searchfield, filters=[['Item Attribute Value', 'attribute_name', '=', attribute]])
		values = frappe.response['values']
		del frappe.response['values']
		return values

	item = frappe.get_doc("Item", item_name)
	attributes = [attribute.attribute for attribute in item.attributes]
	if attribute not in attributes:
		return []
	for attr_obj in item.attributes:
		if attribute == attr_obj.attribute:
			mapping_doc = frappe.get_doc("Item Item Attribute Mapping", attr_obj.mapping)
			if len(mapping_doc.values) == 0:
				search_widget(doctype=doctype, txt=txt, page_length=page_len, searchfield=searchfield, filters=[['Item Attribute Value', 'attribute_name', '=', attribute]])
				values = frappe.response['values']
				del frappe.response['values']
				return values
			else:
				attribute_values = [value.attribute_value for value in mapping_doc.values]
				return [[value] for value in attribute_values if value.lower().startswith(txt.lower())]
		
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_item_attributes(doctype, txt, searchfield, start, page_len, filters):
	if (doctype != 'Item Attribute' or filters['item'] == None):
		return []
	
	item_name = filters['item']
	item = frappe.get_doc("Item", item_name)
	attributes = [attribute.attribute for attribute in item.attributes]
	return [[value] for value in attributes if value.lower().startswith(txt.lower())]

@frappe.whitelist()
def get_attribute_values(item, attributes = None):
	item_doc = frappe.get_doc("Item", item)
	attribute_values = {}

	if not attributes:
		attributes = [attr.attribute for attr in item_doc.attributes]

	for attribute in item_doc.attributes:
		if attribute.attribute in attributes and attribute.mapping != None:
			doc = frappe.get_doc("Item Item Attribute Mapping", attribute.mapping)
			attribute_values[attribute.attribute] = [d.attribute_value for d in doc.values]
	
	return attribute_values

def validate_is_stock_item(item, is_stock_item=None):
	if not is_stock_item:
		is_stock_item = frappe.db.get_value("Item", item, "is_stock_item")

	if is_stock_item != 1:
		frappe.throw(_("Item {0} is not a stock Item").format(item))

def validate_cancelled_item(item, docstatus=None):
	if docstatus is None:
		docstatus = frappe.db.get_value("Item", item, "docstatus")

	if docstatus == 2:
		frappe.throw(_("Item {0} is cancelled").format(item))

def validate_disabled(item, disabled=None):
	if (disabled is None):
		disabled = frappe.db.get_value("Item", item, "disabled")

	if disabled:
		frappe.throw(_("Item {0} is disabled").format(item))

@frappe.whitelist()
def rename_item(docname, name, brand = None):
	print(name, brand)
	doc = frappe.get_doc('Item', docname)
	doc.check_permission(permtype="write")

	transformed_name = doc.get_name(brand, name)
	name_updated = transformed_name and (transformed_name != doc.name)
	doc.name1 = name
	doc.brand = brand
	doc.save()

	if name_updated:
		doc.rename(transformed_name, force=True)

	return doc.name