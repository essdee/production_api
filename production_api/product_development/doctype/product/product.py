# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

from mimetypes import guess_type
import frappe
from frappe.utils import cint
from frappe.model.document import Document

class Product(Document):
	pass

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
		print("Created folder for doctype", doctype_folder.name)
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
		print("Created folder for docname", docname_folder.name)
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