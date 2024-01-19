# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import requests
from requests import Response

import frappe
from frappe.model.document import Document

class MRPSettings(Document):
	pass

def post_erp_request(endpoint: str, data: dict) -> Response:
	config = frappe.get_single('MRP Settings')
	if not config.erp_site_url or not config.erp_api_key or not config.get_password("erp_api_secret"):
		frappe.throw("Please Configure ERP properly")
	url = f"{config.erp_site_url}{endpoint}"
	authorization = f"token {config.erp_api_key}:{config.get_password('erp_api_secret')}"
	headers = {
		'Accept': 'application/json',
		'Authorization': authorization
	}
	response = requests.post(url, headers=headers, json=data)
	return response