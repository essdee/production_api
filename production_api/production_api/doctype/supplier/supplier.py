# Copyright (c) 2021, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.contacts.address_and_contact import load_address_and_contact, delete_contact_and_address

class Supplier(Document):

	def load_item_price_list(self):
		"""Load Item Price List into `__onload`"""
		filters = {"supplier": self.name}
		item_price_list = frappe.get_list("Item Price", filters=filters, fields=["*"])
		self.set_onload('item_price_list', item_price_list)
	
	def onload(self):
		"""Load address and contacts in `__onload`"""
		load_address_and_contact(self)
		self.load_item_price_list()

	def on_trash(self):
		delete_contact_and_address('Supplier', self.name)
