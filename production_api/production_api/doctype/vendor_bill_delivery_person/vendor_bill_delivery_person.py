# Copyright (c) 2025, Aerele Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document


class VendorBillDeliveryPerson(Document):

	def validate(self):
		self.validate_mobile_number()
	
	def validate_mobile_number(self):
		if not self.mobile_no:
			frappe.throw("Mobile number is required")
		if not re.fullmatch(r'[6-9]\d{9}', self.mobile_no):
			frappe.throw("Invalid mobile number. It must be a 10-digit Indian mobile number starting with 6-9.")

@frappe.whitelist()
def get_last_ten_delivery_persons(supplier=None, search=''):
	if not supplier:
		return []
	if not search:
		sql = """
			SELECT t1.delivery_person, t1.delivery_mob_no
			FROM `tabVendor Bill Tracking` t1
			INNER JOIN (
				SELECT delivery_mob_no, MAX(creation) AS max_creation
				FROM `tabVendor Bill Tracking`
				WHERE supplier = %(supplier)s
				GROUP BY delivery_mob_no
			) t2
			ON t1.delivery_mob_no = t2.delivery_mob_no AND t1.creation = t2.max_creation
			ORDER BY t1.creation DESC
			LIMIT 5
		"""
		return frappe.db.sql(sql, {"supplier": supplier}, as_dict=True)

	return frappe.db.sql("""
		SELECT mobile_no AS delivery_mob_no, person_name AS delivery_person
		FROM `tabVendor Bill Delivery Person`
		WHERE mobile_no LIKE %(search)s or person_name LIKE %(search)s
		LIMIT 10
	""", {
		"supplier": supplier,
		"search": f"%{search}%"
	}, as_dict=True)

