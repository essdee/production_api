# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

from mimetypes import guess_type
import frappe
from frappe.utils import cint, get_url
from frappe.model.document import Document
from production_api.utils import update_if_string_instance

class Product(Document):
	def load_costing_list(self):
		"""Load Lotwise Item Profit List into `__onload`"""
		fields = ["name", "product", "total_qty", "avg_rate_per_piece", "profit_percent_markdown"]
		filters = {"product": self.name}
		costing_list = frappe.get_list("Lotwise Item Profit", fields=fields, filters=filters)
		self.set_onload('costing_list', costing_list)

	def onload(self):
		"""Load Attribute List into `__onload`"""
		self.load_costing_list()
		if len(self.product_placement) > 0:
			upload_data = get_table_onload_data(self.product_placement)
			self.set_onload("placement_images", upload_data)	
		
		if len(self.trims) > 0:
			upload_data = get_table_onload_data(self.trims)
			self.set_onload("trims_images", upload_data)	

		if len(self.product_trim_combination) > 0:
			upload_data = get_table_onload_data(self.product_trim_combination, with_list=True)
			self.set_onload("trims_combination", upload_data)	

		if len(self.product_measurement_descriptions) > 0:
			measurement_details = {}
			for row in self.product_measurement_descriptions:
				measurement_details.setdefault(row.group, [])
				measurement_details[row.group].append(row.description)
			self.set_onload("measurement_details", measurement_details)	

	def before_validate(self):
		image_list = []
		if self.get('placement_images'):
			placement_images = update_if_string_instance(self.placement_images)
			image_list = get_tabel_struct_data(placement_images)
		self.set("product_placement", image_list)	
		image_list = []
		if self.get('product_trims_images'):
			trims = update_if_string_instance(self.product_trims_images)
			image_list = get_tabel_struct_data(trims)
		self.set("trims", image_list)	
		image_list = []
		if self.get("trim_comb"):
			trim_comb = update_if_string_instance(self.trim_comb)
			image_list = get_tabel_struct_data(trim_comb, with_list=True)	
		self.set("product_trim_combination", image_list)
		if self.get("measurement_details"):
			measurement_details = update_if_string_instance(self.measurement_details)
			items_list = []
			for key in measurement_details:
				for val in measurement_details[key]:
					items_list.append({
						"description": val,
						"group": key
					})
			self.set("product_measurement_descriptions", items_list)		

def get_table_onload_data(table, with_list=False):
	upload_data = []
	for row in table:
		d = {
			"image_url": get_url(row.url),
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

@frappe.whitelist()
def upload_product_file():
	files = frappe.request.files
	is_private = frappe.form_dict.is_private
	doctype = frappe.form_dict.doctype
	docname = frappe.form_dict.docname
	fieldname = frappe.form_dict.fieldname
	file_url = frappe.form_dict.file_url
	folder = frappe.form_dict.folder or "Home"
	method = frappe.form_dict.method
	filename = frappe.form_dict.file_name
	optimize = frappe.form_dict.optimize
	content = frappe.local.uploaded_file

	file_type = filename.split("_")[1]

	product = frappe.get_doc(doctype, docname)
	product_files = product.get("product_file_versions")
	if not product_files:
		product_files = []
		product.set("product_file_versions", product_files)
	
	files_of_type = [f for f in product_files if f.product_upload_type == file_type]
	version = len(files_of_type) + 1

	extension = filename.split(".")[-1]
	filename = f"{product.name}_{file_type}_{version}"
	if extension:
		filename = f"{filename}.{extension}"
	
	folder = get_or_create_product_folder(doctype, docname)
	file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"attached_to_doctype": doctype,
				"attached_to_name": docname,
				"attached_to_field": fieldname,
				"folder": folder,
				"file_name": filename,
				"file_url": file_url,
				"is_private": cint(is_private),
				"content": content,
			}
		)
	file_doc.save(ignore_permissions=True)
	# create a new row in product_file_versions
	product_file_row = {
		"product_upload_type": file_type,
		"file": file_doc.name,
		"filename": filename,
		"file_url": file_doc.file_url,
		"version_number": version,
		"timestamp": file_doc.creation,
	}
	if product.get("product_file_versions"):
		product.append("product_file_versions", product_file_row)
	else:
		product.set("product_file_versions", [product_file_row])
	product.save()
	return file_doc

def get_or_create_product_folder(doctype, docname):
	# Convert doctype and docname to lowercase and remove spaces and other characters not allowed in folder names
	# Check if doctype folder exists
	# If not create it
	# Check if docname folder exists
	# If not create it
	# Return the folder name

	doctype = doctype.lower().replace(" ", "_")
	docname = docname.lower().replace(" ", "_")
	# Create folder for doctype with parent folder as "Home"
	doctype_folder_name = frappe.get_value(
		"File",
		{
			"file_name": doctype,
			"is_folder": 1,
			"folder": "Home",
		},
		"name",
	)
	if not doctype_folder_name:
		doctype_folder = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": doctype,
				"is_folder": 1,
				"folder": "Home",
			}
		)
		doctype_folder.save(ignore_permissions=True)
		doctype_folder_name = doctype_folder.name

	# Create folder for docname with parent folder as doctype
	docname_folder_name = frappe.db.exists(
		"File",
		{
			"file_name": docname,
			"is_folder": 1,
			"folder": doctype_folder_name,
		},
	)
	if not docname_folder_name:
		docname_folder = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": docname,
				"is_folder": 1,
				"folder": doctype_folder_name,
			}
		)
		docname_folder.save(ignore_permissions=True)
		docname_folder_name = docname_folder.name

	return docname_folder_name

def get_latest_product_images(product_name):
	product = frappe.get_doc("Product", product_name)
	product_files = product.get("product_file_versions")
	# return latest image of each upload type
	grouped_files = get_grouped_files(product_files)
	latest_files = [ group[0] for group in grouped_files.values() ]
	product_images = []
	for file in latest_files:
		content_type = guess_type(file.filename)[0]
		if content_type and content_type.startswith("image/"):
			product_images.append(file)

	return product_images

def get_grouped_files(files):
	# Group files by product_upload_type
	grouped_files = {}
	for file in files:
		if file.product_upload_type not in grouped_files:
			grouped_files[file.product_upload_type] = []
		grouped_files[file.product_upload_type].append(file)
	# sort files by version number in descending order
	for key in grouped_files:
		grouped_files[key].sort(key=lambda x: x.version_number, reverse=True)
	return grouped_files

@frappe.whitelist()
def get_product_colour_codes(docname):
	doc = frappe.get_doc("Product", docname)
	colour_codes = {}
	if doc.is_set_item:
		for row in doc.product_set_colours:
			colour_codes[row.top_colour] = row.top_colour_code
			colour_codes[row.bottom_colour] = row.bottom_colour_code
	else:
		for row in doc.product_colours:
			colour_codes[row.product_colour] = row.colour_code
	return colour_codes		
