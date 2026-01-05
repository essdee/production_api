# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

from mimetypes import guess_type
import frappe
from frappe.utils import cint, get_url
from frappe.model.document import Document
from production_api.utils import update_if_string_instance

class ProductRelease(Document):
	def onload(self):
		"""Load Attribute List into `__onload`"""
		if len(self.product_placement) > 0:
			upload_data = get_table_onload_data(self.product_placement)
			self.set_onload("placement_images", upload_data)	
		
		if len(self.trims) > 0:
			upload_data = get_table_onload_data(self.trims)
			self.set_onload("trims_images", upload_data)	

		if len(self.product_trim_combination) > 0:
			upload_data = get_table_onload_data(self.product_trim_combination, with_list=True)
			self.set_onload("trims_combination", upload_data)	

		if len(self.product_accessories) > 0:
			upload_data = get_table_onload_data(self.product_accessories)
			self.set_onload("accessory_images", upload_data)	

		if len(self.product_measurement_descriptions) > 0:
			measurement_details = {}
			for row in self.product_measurement_descriptions:
				measurement_details.setdefault(row.group, [])
				measurement_details[row.group].append(row.description)
			self.set_onload("measurement_details", measurement_details)	

def get_table_onload_data(table, with_list=False):
	upload_data = []
	for row in table:
		d = {
			"image_url": get_url(frappe.get_value("Product Image", row.product_image, "image")),
			"image_title": row.title_header,
			"image_name": row.product_image
		}
		if with_list:
			d['selected_colours'] = row.selected_colours.split(",")
		upload_data.append(d)
	return upload_data
	
def get_tabel_struct_data(data, with_list=False):
	image_list = []
	for row in data:
		d = {
			"product_image": row['image_name'],
			"url": row['image_url'],
			"title_header": row['image_title'],
		}
		if with_list:
			d['selected_colours'] = ",".join(row.get("selected_colours") or [])
		image_list.append(d)
	return image_list
