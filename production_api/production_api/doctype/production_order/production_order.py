# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import date_diff
from frappe.model.document import Document
from production_api.utils import update_if_string_instance, get_variant_attr_details
from production_api.production_api.doctype.item.item import get_attribute_details, get_or_create_variant

class ProductionOrder(Document):
	def before_submit(self):
		self.posting_date = frappe.utils.nowdate()
			
	def onload(self):
		order_qty = get_order_qty(self.production_order_details)
		self.set_onload("items", order_qty)		
		ordered_detail = get_ordered_details(self.production_ordered_details)
		self.set_onload("ordered_details", {
			"items": order_qty,
			"ordered": ordered_detail
		})

	def before_validate(self):
		if not self.is_new() and self.get("item_details"):
			self.update_order()
		self.lead_time_given = date_diff(self.delivery_date, self.posting_date)

	def update_order(self):
		item_fields = ["primary_attribute", "dependent_attribute", "default_unit_of_measure"]
		primary, dependent, uom = frappe.get_value("Item", self.item, item_fields)
		item_details = update_if_string_instance(self.item_details)
		items = []
		for item in item_details:
			variant = get_or_create_variant(self.item, {dependent: "Pack",primary: item})
			item1 = {}
			item1['item_variant'] = variant
			item1['quantity'] = item_details[item].get('qty', 0)
			item1['ratio'] = item_details[item].get('ratio', 0)
			item1['mrp'] = item_details[item].get('mrp', 0)
			item1['wholesale_price'] = item_details[item].get('wholesale', 0)
			item1['retail_price'] = item_details[item].get('retail', 0)
			item1['uom'] = uom
			items.append(item1)
		self.set("production_order_details", items)

@frappe.whitelist()
def get_primary_values(item):
	item_doc = frappe.get_cached_doc("Item", item)
	if not item_doc.primary_attribute or not item_doc.dependent_attribute:
		frappe.throw(f"Can't Create Production Order for Item {item}")
	attr_details = get_attribute_details(item)
	return attr_details['primary_attribute_values']

@frappe.whitelist()
def get_order_qty(items):
	items = [item.as_dict() for item in items]
	order_qty = {}
	for row in items:
		current_variant = frappe.get_cached_doc("Item Variant", row['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		primary_attribute = current_item_attribute_details['primary_attribute']
		for attr in current_variant.attributes:
			if attr.attribute == primary_attribute:
				order_qty.setdefault(attr.attribute_value, {
					"qty": 0,
					"ratio": 0,
					"mrp": 0,
					"wholesale": 0,
					"retail": 0,
				})
				order_qty[attr.attribute_value]['qty'] += row['quantity']
				order_qty[attr.attribute_value]['ratio'] += row['ratio']
				order_qty[attr.attribute_value]['mrp'] += row['mrp']
				order_qty[attr.attribute_value]['wholesale'] += row['wholesale_price']
				order_qty[attr.attribute_value]['retail'] += row['retail_price']
				break	
	return order_qty		

def get_ordered_details(items):
	items = [item.as_dict() for item in items]
	lot_wise_detail = {}
	for row in items:
		lot_wise_detail.setdefault(row['lot'], {})
		current_variant = frappe.get_cached_doc("Item Variant", row['item_variant'])
		current_item_attribute_details = get_attribute_details(current_variant.item)
		primary_attribute = current_item_attribute_details['primary_attribute']
		for attr in current_variant.attributes:
			if attr.attribute == primary_attribute:
				lot_wise_detail[row['lot']].setdefault(attr.attribute_value, {
					"qty": 0,
				})
				lot_wise_detail[row['lot']][attr.attribute_value]['qty'] += row['quantity']
				break	
	return lot_wise_detail

@frappe.whitelist()
def get_production_order_details(production_order):
	doc = frappe.get_doc("Production Order", production_order)
	order_qty = get_order_qty(doc.production_order_details)
	return order_qty

@frappe.whitelist()
def update_price(production_order, item_details):
	doc = frappe.get_doc("Production Order", production_order)
	item_details = update_if_string_instance(item_details)
	primary = frappe.get_value("Item", doc.item, "primary_attribute")
	for size in item_details:
		for row in doc.production_order_details:
			attrs = get_variant_attr_details(row.item_variant)
			if attrs[primary] == size:
				row.mrp = item_details[size]['mrp']
				row.wholesale_price = item_details[size]['wholesale']
				row.retail_price = item_details[size]['retail']
				break
	doc.save(ignore_permissions=True)

@frappe.whitelist()
def create_lot(production_order, lot_name):
	if frappe.db.exists("Lot", lot_name):
		frappe.throw(frappe._("Lot Name {0} already exists").format(lot_name))
	
	po_doc = frappe.get_doc("Production Order", production_order)
	
	lot = frappe.new_doc("Lot")
	lot.lot_name = lot_name
	lot.production_order = production_order
	lot.item = po_doc.item
	lot.status = "Open"
	lot.insert(ignore_permissions=True)
	
	return lot.name

@frappe.whitelist()
def link_lot(production_order, lot_name):
	lot = frappe.get_doc("Lot", lot_name)
	if lot.item:
		frappe.throw("Item is already Linked in this Lot")
	po_doc = frappe.get_doc("Production Order", production_order)
	lot.production_order = production_order
	lot.item = po_doc.item
	lot.status = "Open"
	lot.save(ignore_permissions=True)
	return lot.name
