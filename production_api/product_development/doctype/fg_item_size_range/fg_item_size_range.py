# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

class FGItemSizeRange(Document):
	def validate(self):
		if not self.uid:
			frappe.throw(_("UID is required."))
		# Check if the uid is unique if new.
		if self.is_new():
			if frappe.db.exists({"doctype": "FG Item Size Range", "uid": self.uid}):
				frappe.throw(_("UID {0} already exists.").format(self.uid))

def get_sizes(size_range):
	doc = frappe.get_doc("FG Item Size Range", size_range)
	return [s.attribute_value for s in doc.sizes]
