# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.contacts.address_and_contact import load_address_and_contact, delete_contact_and_address
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.contacts.doctype.contact.contact import get_default_contact
from jinja2 import TemplateSyntaxError
from production_api.production_api.doctype.item_price.item_price import get_all_active_price
from spine.spine_adapter.handler.default_consumer_handler import DocDoesNotExist, DocTypeNotAvailable, IncorrectData, UnknownEvent, get_module_logger

class Supplier(Document):

	def load_item_price_list(self):
		"""Load Item Price List into `__onload`"""
		item_price_list = get_all_active_price(supplier = self.name)
		item_prices = []
		for price in item_price_list:
			doc = frappe.get_doc("Item Price", price.name)
			item_prices.append(doc)
		self.set_onload('item_price_list', item_prices)
	
	def onload(self):
		"""Load address and contacts in `__onload`"""
		load_address_and_contact(self)
		self.load_item_price_list()

	def on_trash(self):
		delete_contact_and_address('Supplier', self.name)
	
	def send_notification(self, doctype: str, docname: str, channels: list[str], event: str):
		# get contact information from supplier
		contact_name = get_default_contact(self.doctype, self.name)
		if not contact_name:
			frappe.throw(_("Please set a default contact for this supplier"))
		contact = frappe.get_doc("Contact", contact_name)
		# Get Primary Email from email_ids
		primary_email = None
		if contact.email_ids:
			primary_emails = [email.email_id for email in contact.email_ids if email.is_primary == 1]
			if primary_emails:
				primary_email = primary_emails[0]
		
		# Get Primary Mobile from phone_nos
		primary_mobile = None
		if contact.phone_nos:
			primary_mobiles = [phone.phone for phone in contact.phone_nos if phone.is_primary_mobile_no == 1]
			if primary_mobiles:
				primary_mobile = primary_mobiles[0]
		# get all notification template for the doctype and channel
		filters = {
			"document_type": doctype,
			"channel": ["in", channels],
			"event": event,
			"enabled": 1
		}
		notificaton_templates = frappe.get_all("Notification Template", filters=filters)

		# send notification
		for template in notificaton_templates:
			template = frappe.get_doc("Notification Template", template.name)
			if template.channel == "Email" and primary_email:
				template.send(docname, event, [primary_email])
			elif template.channel == "SMS" and primary_mobile:
				template.send(docname, event, [primary_mobile])
		pass

def make_gstin_custom_field():
	custom_fields = {
		'Address': [
			dict(fieldname='gstin', label='GSTIN', fieldtype='Data',
				insert_after='fax'),
		]
	}
	create_custom_fields(custom_fields)
	make_property_setter('Address', 'county', 'hidden', 1, 'Check')

@frappe.whitelist()
def get_primary_address(supplier):
	filters = [
		["Dynamic Link", "link_doctype", "=", "Supplier"],
		["Dynamic Link", "link_name", "=", supplier],
		["Dynamic Link", "parenttype", "=", "Address"],
		["Address", "disabled", "=", "0"],
		["Address", "is_primary_address", "=", 1]
	]

	address = frappe.get_list("Address", filters=filters, pluck="name") or {}

	if address:
		return address[0]
	
@frappe.whitelist()
def get_address(supplier, type):
	filters = [
		["Dynamic Link", "link_doctype", "=", "Supplier"],
		["Dynamic Link", "link_name", "=", supplier],
		["Dynamic Link", "parenttype", "=", "Address"],
		["Address", "disabled", "=", "0"],
		["Address", "address_type", "=", type]
	]

	address = frappe.get_list("Address", filters=filters, pluck="name") or {}

	if address:
		return address[0]

@frappe.whitelist()
def get_supplier_address_display(supplier):
	address_dict = get_primary_address(supplier)
	if not address_dict:
		return

	if not isinstance(address_dict, dict):
		address_dict = frappe.db.get_value("Address", address_dict, "*", as_dict=True, cache=True) or {}

	# name, template = get_address_templates(address_dict)
	template = '''
		{{ address_line1 }}, {% if address_line2 %}{{ address_line2 }}{% endif -%}<br>
		{{ city }}, {% if state %}{{ state }}{% endif -%}{% if pincode %} - {{ pincode }}{% endif -%}
	'''

	try:
		return frappe.render_template(template, address_dict)
	except TemplateSyntaxError:
		frappe.throw(_("There is an error in your Address Template"))


# ---------------------------------
# Spine Sync handler for supplier
# ---------------------------------
def handler(payload, raise_error = True):
	try:
		logger = get_module_logger()
		incoming_doctype = payload.get("Header").get("DocType")
		if incoming_doctype != "Supplier": raise Exception("This handler only handles Supplier DocType")
		logger.debug(incoming_doctype)
		if not incoming_doctype or not frappe.db.exists("DocType", incoming_doctype):
			logger.debug("Doctype does not Exist ->", incoming_doctype)
			if raise_error:
				raise DocTypeNotAvailable(incoming_doctype)
			else:
				return None
		event = payload.get("Header").get("Event")
		logger.debug("Handling Event -> {}".format(event))
		if event in ["on_update"]:
			handle_update(payload)
		elif event in ["after_insert", "first_sync"]:
			handle_insert(payload)
		elif event == "on_trash":
			handle_remove(payload)
		elif event == "after_rename":
			handle_rename(payload)
		else:
			logger.debug("Did not find event "+event)
			if raise_error:
				raise UnknownEvent(event)
			else:
				return None
	except:
		if raise_error:
			raise

def get_local_doc(doctype, uid):
	"""Get the local document if created with a different name"""
	if not doctype or not uid:
		return None
	try:
		doc_list = frappe.get_list(doctype, filters={"uid":uid}, pluck="name")
		if len(doc_list) > 0:
			return frappe.get_doc(doctype, doc_list[0])
		else: return None
	except frappe.DoesNotExistError:
		return None
	
def remove_payload_fields(payload):
	remove_fields = ["modified", "creation", "modified_by", "owner", "idx"]
	for f in remove_fields:
		if payload.get(f):
			del payload[f]
	return payload
		
def handle_update(payload):
	"""Sync update type update"""
	logger = get_module_logger()
	doctype = payload.get("Header").get("DocType")
	docname = payload.get("Payload").get("name")
	uid = payload.get("Payload").get("uid")
	if not doctype or not uid:
		raise IncorrectData(msg="Incorrect Data passed")
	local_doc = get_local_doc(doctype, uid)
	logger.debug("Updating {}".format(docname))
	logger.debug(local_doc)
	if local_doc:
		data = frappe._dict(payload.get('Payload'))
		if data.name != local_doc.name:
			logger.debug("Renaming doc in update")
			local_doc.rename(data.name, force=True)
		remove_payload_fields(data)
		local_doc.update(data)
		logger.debug("Saving doc")
		local_doc.save()
		local_doc.db_update_all()
	else:
		raise DocDoesNotExist(doctype, docname)

def handle_insert(payload):
	doctype = payload.get("Header").get("DocType")
	docname = payload.get("Payload").get("name")
	uid = payload.get("Payload").get("uid")
	if not doctype or not uid:
		raise IncorrectData(msg="Incorrect Data passed")
	if frappe.db.exists(doctype, {"uid": uid}):
		raise Exception("Document already exists")
	
	data = frappe._dict(payload.get("Payload"))
	remove_payload_fields(data)
	doc = frappe.get_doc(data)
	doc.insert(set_name=docname, set_child_names=False)
	return doc

def handle_remove(payload):
	doctype = payload.get("Header").get("DocType")
	docname = payload.get("Payload").get("name")
	uid = payload.get("Payload").get("uid")
	if not doctype or not uid:
		raise IncorrectData(msg="Incorrect Data passed")
	local_doc = get_local_doc(doctype, uid)
	if local_doc:
		local_doc.remove()

def handle_rename(payload):
	doctype = payload.get("Header").get("DocType")
	publish_doc = payload.get("Payload")
	rename_meta = publish_doc.get("rename_meta")
	if rename_meta:
		local_doc = get_local_doc(doctype, rename_meta.get("old_name"))
		if local_doc:
			local_doc.rename(name=rename_meta.get("new_name"),  merge=rename_meta.get("merge"), force=True)
	else:
		raise IncorrectData("Incorrect Data Passed")