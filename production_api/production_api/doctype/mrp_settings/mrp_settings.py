# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import requests
from requests import Response

import frappe
from frappe.model.document import Document

class MRPSettings(Document):
	def validate(self):
		if self.fiscal_year_start_date and self.fiscal_year_end_date:
			if self.fiscal_year_end_date < self.fiscal_year_start_date:
				frappe.throw("Please set the fiscal year start and end date correctly")

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

def get_purchase_invoice_series(series:str) -> str:
	mapped_series = None
	config = frappe.get_single('MRP Settings').purchase_invoice_series_map
	for c in config:
		if c.series == series:
			mapped_series = c.mapped_series
			break
	return mapped_series

def get_sales_credentials():
	config = frappe.get_single("MRP Settings")
	if not config.sales_site_url or not config.sales_api_key or not config.sales_api_secret:
		frappe.throw("Please Setup The Sales Credentials")
	return {
		"url" : config.sales_site_url,
		"token" : f"token {config.sales_api_key}:{config.get_password('sales_api_secret')}"
	}