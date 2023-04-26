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
def get_supplier_list():
	suppliers = frappe.db.get_list("Supplier")
	if suppliers:
		return suppliers