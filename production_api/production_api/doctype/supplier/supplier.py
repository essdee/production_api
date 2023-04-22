# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.contacts.address_and_contact import load_address_and_contact, delete_contact_and_address
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.contacts.doctype.contact.contact import get_default_contact
from production_api.production_api.doctype.item_price.item_price import get_all_active_price
import json

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
def update_suppliers(data):
	data = frappe.parse_json(data)
	if isinstance(data, dict):
		data = [data]
	print(json.dumps(data, indent=4))
	# Add to Queue for updating
	for supplier in data:
		supplier_name = supplier.get("supplier").get("name")
		frappe.enqueue('production_api.production_api.doctype.supplier.supplier.update_supplier', supplier_data=supplier, job_name=f"Supplier Sync - {supplier_name}")

@frappe.whitelist()
def update_supplier(supplier_data):
	if isinstance(supplier_data, str):
		supplier_data = frappe.parse_json(supplier_data)
	else:
		supplier_data = frappe._dict(supplier_data)
	supplier = supplier_data.get("supplier")
	addresses = supplier_data.get("addresses")
	contacts = supplier_data.get("contacts")
	if not supplier:
		frappe.throw(_("Supplier is required"))
	
	# Check if supplier uid exists in our system
	supplier_uid = supplier.get("uid")
	if not supplier_uid:
		frappe.throw(_("Supplier UID is required"))
	suppliers = frappe.get_all("Supplier", filters={"uid": supplier_uid}, pluck="name")
	if not suppliers:
		# Create Supplier
		supplier_doc = frappe.get_doc({
			"doctype": "Supplier",
			"supplier_name": supplier.get("supplier_name"),
			"uid": supplier_uid,
			"pan": supplier.get("pan"),
			"disabled": supplier.get("disabled"),
		})
		supplier_doc.insert()
		supplier_doc.save()
		# Create Address
		if addresses:
			for address in addresses:
				address_doc = create_address(address, supplier_doc)
		# Create Contact
		if contacts:
			for contact in contacts:
				contact_doc = create_contact(contact, supplier_doc)
	else:
		# Update Supplier
		supplier_doc = frappe.get_doc("Supplier", suppliers[0])
		supplier_doc.supplier_name = supplier.get("supplier_name")
		supplier_doc.uid = supplier_uid
		supplier_doc.pan = supplier.get("pan")
		supplier_doc.disabled = supplier.get("disabled")
		supplier_doc.save()
		# Update Address
		if addresses:
			for address in addresses:
				address_filters = [
					["Dynamic Link", "link_doctype", "=", "Supplier"],
					["Dynamic Link", "link_name", "=", supplier_doc.name],
					["Dynamic Link", "parenttype", "=", "Address"],
					["Address", "address_title", "=", address.get("address_title")],
					["Address", "address_type", "=", address.get("address_type")]
				]
				current_addresses = frappe.get_all("Address", filters=address_filters, pluck="name")
				if current_addresses:
					address_doc = update_address(current_addresses[0], address, supplier_doc)
				else:
					address_doc = create_address(address, supplier_doc)
		# Update Contact
		if contacts:
			for contact in contacts:
				contact_filters = [
					["Dynamic Link", "link_doctype", "=", "Supplier"],
					["Dynamic Link", "link_name", "=", supplier_doc.name],
					["Dynamic Link", "parenttype", "=", "Contact"],
					["Contact", "first_name", "=", contact.get("first_name")],
					["Contact", "last_name", "=", contact.get("last_name")],
				]
				if not contact.get("last_name"):
					contact_filters.pop()
					contact_filters.append(["Contact", "last_name", "is", "not set"])
				current_contacts = frappe.get_all("Contact", filters=contact_filters, pluck="name")
				if current_contacts:
					contact_doc = update_contact(current_contacts[0], contact, supplier_doc)
				else:
					contact_doc = create_contact(contact, supplier_doc)
	pass

def create_address(address, supplier_doc):
	address_doc = frappe.get_doc({
		"doctype": "Address",
		"address_title": address.get("address_title"),
		"address_type": address.get("address_type"),
		"address_line1": address.get("address_line1"),
		"address_line2": address.get("address_line2"),
		"city": address.get("city"),
		"state": address.get("state"),
		"county": address.get("county"),
		"country": address.get("country"),
		"pincode": address.get("pincode"),
		"gstin": address.get("gstin"),
		"email_id": address.get("email"),
		"phone": address.get("phone"),
		"fax": address.get("fax"),
		"is_primary_address": address.get("is_primary_address"),
		"is_shipping_address": address.get("is_shipping_address"),
		"disabled": address.get("disabled"),
		"links": [{
			"doctype": "Dynamic Link",
			"link_doctype": "Supplier",
			"link_name": supplier_doc.name,
			"link_title": link.get("link_title"),
		} for link in address.get("links")]
	})
	address_doc.insert()
	address_doc.save()
	return address_doc

def update_address(name, address, supplier_doc):
	address_doc = frappe.get_doc("Address", name)
	address_doc.address_title = address.get("address_title")
	address_doc.address_type = address.get("address_type")
	address_doc.address_line1 = address.get("address_line1")
	address_doc.address_line2 = address.get("address_line2")
	address_doc.city = address.get("city")
	address_doc.state = address.get("state")
	address_doc.county = address.get("county")
	address_doc.country = address.get("country")
	address_doc.pincode = address.get("pincode")
	address_doc.gstin = address.get("gstin")
	address_doc.email_id = address.get("email_id")
	address_doc.phone = address.get("phone")
	address_doc.fax = address.get("fax")
	address_doc.is_primary_address = address.get("is_primary_address")
	address_doc.is_shipping_address = address.get("is_shipping_address")
	address_doc.disabled = address.get("disabled")
	# Match already Existing Links with new Links
	for link in address.get("links"):
		link_exists = False
		for existing_link in address_doc.links:
			if existing_link.link_title == link.get("link_title"):
				link_exists = True
		if not link_exists:
			address_doc.append("links", {
				"doctype": "Dynamic Link",
				"link_doctype": "Supplier",
				"link_name": supplier_doc.name,
				"link_title": link.get("link_title"),
			})
	address_doc.save()
	return address_doc

def create_contact(contact, supplier_doc):
	contact_doc = frappe.get_doc({
		"doctype": "Contact",
		"first_name": contact.get("first_name"),
		"middle_name": contact.get("middle_name"),
		"last_name": contact.get("last_name"),
		"email_id": contact.get("email_id"),
		"status": contact.get("status"),
		"designation": contact.get("designation"),
		"gender": contact.get("gender"),
		"phone": contact.get("phone"),
		"mobile_no": contact.get("mobile_no"),
		"company_name": contact.get("company_name"),
		"is_primary_contact": contact.get("is_primary_contact"),
		"department": contact.get("department"),
		"unsubscribed": contact.get("unsubscribed"),
		"links": [{
			"doctype": "Dynamic Link",
			"link_doctype": "Supplier",
			"link_name": supplier_doc.name,
			"link_title": link.get("link_title"),
		} for link in contact.get("links")],
		"email_ids": [{
			"email_id": email.get("email_id"),
			"is_primary": email.get("is_primary"),
		} for email in contact.get("email_ids")],
		"phone_nos": [{
			"phone": phone.get("phone"),
			"is_primary_phone": phone.get("is_primary_phone"),
			"is_primary_mobile_no": phone.get("is_primary_mobile_no"),
		} for phone in contact.get("phone_nos")],
	})
	contact_doc.insert()
	contact_doc.save()
	return contact_doc

def update_contact(name, contact, supplier_doc):
	contact_doc = frappe.get_doc("Contact", name)
	contact_doc.first_name = contact.get("first_name")
	contact_doc.middle_name = contact.get("middle_name")
	contact_doc.last_name = contact.get("last_name")
	contact_doc.email_id = contact.get("email_id")
	contact_doc.status = contact.get("status")
	contact_doc.designation = contact.get("designation")
	contact_doc.gender = contact.get("gender")
	contact_doc.phone = contact.get("phone")
	contact_doc.mobile_no = contact.get("mobile_no")
	contact_doc.company_name = contact.get("company_name")
	contact_doc.is_primary_contact = contact.get("is_primary_contact")
	contact_doc.department = contact.get("department")
	contact_doc.unsubscribed = contact.get("unsubscribed")
	# Match already Existing Links with new Links
	for link in contact.get("links"):
		link_exists = False
		for existing_link in contact_doc.links:
			if existing_link.link_title == link.get("link_title"):
				link_exists = True
		if not link_exists:
			contact_doc.append("links", {
				"doctype": "Dynamic Link",
				"link_doctype": "Supplier",
				"link_name": supplier_doc.name,
				"link_title": link.get("link_title"),
			})
	# Match already Existing Email IDs with new Email IDs
	for email in contact.get("email_ids"):
		email_exists = False
		for existing_email in contact_doc.email_ids:
			if existing_email.email_id == email.get("email_id"):
				email_exists = True
				existing_email.is_primary = email.get("is_primary")
				break
		if not email_exists:
			contact_doc.append("email_ids", {
				"doctype": "Contact Email",
				"email_id": email.get("email_id"),
				"is_primary": email.get("is_primary"),
			})
	# Match already Existing Phone Nos with new Phone Nos
	for phone in contact.get("phone_nos"):
		phone_exists = False
		for existing_phone in contact_doc.phone_nos:
			if existing_phone.phone == phone.get("phone"):
				phone_exists = True
				existing_phone.is_primary_phone = phone.get("is_primary_phone")
				existing_phone.is_primary_mobile_no = phone.get("is_primary_mobile_no")
				break
		if not phone_exists:
			contact_doc.append("phone_nos", {
				"doctype": "Contact Phone",
				"phone": phone.get("phone"),
				"is_primary_phone": phone.get("is_primary_phone"),
				"is_primary_mobile_no": phone.get("is_primary_mobile_no"),
			})
	contact_doc.save()
	return contact_doc