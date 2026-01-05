# Copyright (c) 2025, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url
from frappe.model.document import Document


class ProductImage(Document):
	pass

@frappe.whitelist()
def get_image_list(query):
	records = frappe.get_all(
		"Product Image",
		filters={"name": ["like", f"%{query}%"]},
		fields=["name", "image", "title_header"]
	)
	result = []
	for r in records:
		result.append({
			"image_url": get_url(r.image),
			"image_title": r.title_header,
			"image_name": r.name
		})

	return result
