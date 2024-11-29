# Copyright (c) 2024, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WorkStation(Document):
	def before_validate(self):
		if self.default:
			ws_list = frappe.db.sql(
				f"""
					Select name from `tabWork Station` where action = '{self.action}' and `default` = 1 order by creation desc LIMIT 1
				""", as_dict = True
			)
			if ws_list:
				frappe.throw(f"Work Station {ws_list[0]['name']} exist for Action {self.action}")
