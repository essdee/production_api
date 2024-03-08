# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

from six import string_types
import json

import frappe
from frappe.model.document import Document
from frappe.utils.data import cint, get_link_to_form
from production_api.product_development.doctype.fg_item_settings.fg_item_settings import get_dc_details, get_oms_details, make_get_request, make_post_request
from production_api.production_api.doctype.item.item import create_variant, get_or_create_variant, rename_item
from production_api.production_api.doctype.item_dependent_attribute_mapping.item_dependent_attribute_mapping import get_dependent_attribute_details
from production_api.product_development.doctype.fg_item_size_range.fg_item_size_range import get_sizes

class FGItemMaster(Document):
	def validate(self):
		if frappe.flags.in_patch:
			return
		self.validate_sizes()
		sizes = [size.attribute_value for size in self.sizes]
		self.set("available_sizes", ",".join(sizes))
	
	def validate_sizes(self):
		size_range = self.size_range
		if not size_range:
			frappe.throw("Please set size range")
		sizes = get_sizes(size_range)
		c_sizes = [size.attribute_value for size in self.sizes]
		if sizes != c_sizes:
			self.set("sizes", [frappe._dict({"attribute_value": s}) for s in sizes])
	
	# function that is used to sync the item with other systems
	def sync_item(self, rename=False):
		push_enabled = frappe.db.get_single_value("FG Item Settings", "enable_auto_update")
		if not push_enabled:
			return
		if rename:
			if self.item:
				sync_rename_item(self.item, self.name, brand=self.brand)
		else:
			create_or_update_item(self)
		updated = sync_FG_item_OMS(self.name)
		if not updated:
			frappe.throw("Some error occurred")
		try:
			sync_FG_item_DC(self.name)
		except:
			pass

@frappe.whitelist()
def sync_fg_item(name):
	doc = frappe.get_doc("FG Item Master", name)
	doc.sync_item()

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
		"item_group": "Products",
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

def get_item_for_oms(item_name):
	item = frappe.get_doc("FG Item Master", item_name)
	uid: str = item.uid or ""
	if len(uid.split('-')) == 2:
		uid = cint(uid.split("-")[1])
	else:
		uid = None
	
	dc_uid: str = item.dc_uid or ""
	if len(dc_uid.split('-')) == 2:
		dc_uid = cint(dc_uid.split("-")[1])
	else:
		dc_uid = None

	return {
		"iditem": uid,
		"name": item.name1,
		"sizerange": frappe.get_value("FG Item Size Range", item.size_range, "uid"),
		"pieces": item.pcs_per_box,
		"boxespercarton": item.box_per_carton,
		"category": item.category,
		"HSN": item.hsn,
		"status": "inactive" if item.disabled else "active" ,
		"deprecated": item.deprecated,
		"dc_id": dc_uid,
		"brand": item.brand1
	}

def sync_FG_item_OMS(item):
	item_name = item
	item = get_item_for_oms(item)
	oms_details = get_oms_details()
	if not item.get("brand") or not oms_details.get(item.get("brand")):
		return
	
	oms_detail = oms_details.get(item.get("brand"))
	oms_url = oms_detail.get("url")
	oms_api_key = oms_detail.get("api_key")
	oms_api_secret = oms_detail.get("api_secret")
	
	res = None
	create = False
	if not item["iditem"]:
		create = True
		res = make_post_request({'item': item, 'get_db_name': True}, oms_url, "/api/create_item", oms_api_key, oms_api_secret)
	else:
		res = make_post_request({'item': item, 'get_db_name': True}, oms_url, "/api/update_item", oms_api_key, oms_api_secret)
	
	if not res:
		res = {
			"error": True,
			"status": "",
			"message": "Unknown Error",
		}

	if "error" in res and res["error"] == True:
		error = frappe.log_error("Sync with OMS Failed", f"Status -> {res['status']}, Message -> {res['message']}", "FG Item Master", item_name)
		frappe.throw(f"Sync with OMS Failed {get_link_to_form(error.doctype, error.name)}")
	
	if create:
		doc = frappe.get_doc("FG Item Master", item_name)
		doc.uid = f"{res['db_name']}-{res['iditem']}"
		doc.save()
	return True

def sync_FG_item_DC(item):
	item_name = item
	item = get_item_for_oms(item)
	if not item.get("brand"):
		return
	
	dc_detail = get_dc_details()
	dc_url = dc_detail.get("url")
	dc_api_key = dc_detail.get("api_key")
	dc_api_secret = dc_detail.get("api_secret")
	
	item["uid"] = item["iditem"]
	item["naming_series"] = item["brand"].upper()
	item["category"] = "product"

	res = None
	create = False
	dc_id = item["dc_id"]

	if not dc_id:
		create = True
		res = make_post_request({'item': item, 'get_db_name': True}, dc_url, "/api/create_item", dc_api_key, dc_api_secret)
	else:
		item["id"] = dc_id
		res = make_post_request({'item': item, 'get_db_name': True}, dc_url, "/api/update_item", dc_api_key, dc_api_secret)
	
	if not res:
		res = {
			"error": True,
			"status": "",
			"message": "Unknown Error",
		}

	if "error" in res and res["error"] == True:
		error = frappe.log_error("Sync with DC Failed", f"Status -> {res['status']}, Message -> {res['message']}", "FG Item Master", item_name)
		frappe.throw(f"Sync with DC Failed {get_link_to_form(error.doctype, error.name)}")
	
	if create:
		doc = frappe.get_doc("FG Item Master", item_name)
		doc.dc_uid = f"{res['db_name']}-{res['id']}"
		doc.save()
	return True
		
