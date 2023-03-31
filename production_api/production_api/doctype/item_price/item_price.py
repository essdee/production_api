# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe import utils

class ItemPrice(Document):
	def before_validate(self):
		validate_price_values(self.item_price_values)

	def validate_attribute_values(self, qty = 0, attribute = None, attribute_value = None) :
		if self.depends_on_attribute and (attribute == None or self.attribute != attribute or attribute_value == None):
			return None
		price_values = [[price.moq, price.price, price.attribute_value] for price in self.item_price_values]
		price = get_price_value(price_values, qty, attribute_value)
		return price


@frappe.whitelist()
def get_active_price(item: str, supplier: str = None):
	if (item == None):
		return None
	filters = {
		"item_name": item,
		"from_date": ['<=', utils.nowdate()]
	}
	if (supplier != None):
		filters['supplier'] = supplier
	lst = frappe.db.get_list(
		'Item Price',
		filters=filters,
	)
	if len(lst) == 0:
		frappe.throw("No Active Price List")
	
	if len(lst) > 1:
		for l in lst[1:]:
			d = frappe.get_doc('Item Price', l.name)
			# Todo: Set status to disabled
	
	d = frappe.get_doc('Item Price', lst[0].name)
	return d

def validate_price_values(item_price_values):
	values = []
	for price in item_price_values:
		unique_value = ', '.join([str(price.moq), str(price.attribute_value)])
		if unique_value in values:
			frappe.throw('Duplicate Entries Found')
		else:
			values.append(unique_value)

def get_price_value(item_price_values, qty = 0, attribute_value = None):
	"""
	Get Item Price Value for the qty and the attribute value from item_price_values
	:param item_price_values: as List of List
		item_price_values = [
			[moq, price, attribute],
			[0, 100, None],
			[10, 98, '20 Dia']
		]
	"""
	moq = -1
	rate = -1
	print(item_price_values)
	for price in item_price_values:
		print(price)
		if price[2] == attribute_value and (moq < price[0] and price[0] <= qty):
			print(price[2])
			moq = price[0]
			rate = price[1]
	print(moq)
	if (moq != -1):
		return rate
	return None

@frappe.whitelist()
def get_item_supplier_price(item_detail, supplier: str = None):
	if (item_detail == None or supplier == None):
		return None
	if (type(item_detail) is str):
		item_detail = json.loads(item_detail)
	print(json.dumps(item_detail, indent=3))
	print("")
	item_price = None
	try:
		item_price = get_active_price(item_detail["name"], supplier)
	except:
		return None

	if (item_price != None):
		if item_price.depends_on_attribute:
			if item_price.attribute in item_detail["attributes"].keys():
				qty_sum = 0
				for qty_key in item_detail["values"].keys():
					qty_sum += item_detail["values"][qty_key]["qty"]
				price = item_price.validate_attribute_values(qty=qty_sum, attribute = item_price.attribute, attribute_value = item_detail["attributes"][item_price.attribute])
				return price
			elif item_price.attribute == item_detail["primary_attribute"]:
				prices = {}
				for qty_key in item_detail["values"].keys():
					qty = item_detail["values"][qty_key]["qty"]
					price = item_price.validate_attribute_values(qty=qty, attribute = item_price.attribute, attribute_value = qty_key)
					prices[qty_key] = price
				return prices
			else:
				return None
		else:
			qty_sum = 0
			for qty_key in item_detail["values"].keys():
				qty_sum += item_detail["values"][qty_key]["qty"]
			price = item_price.validate_attribute_values(qty=qty_sum)
			return price
