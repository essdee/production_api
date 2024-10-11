# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests

class FGItemSettings(Document):
	pass

def get_oms_details():
	l = frappe.get_single("FG Item Settings")
	oms = {}
	for d in l.get("oms"):
		oms[d.brand] = d.as_dict()
		oms[d.brand]["api_secret"] = d.get_password("api_secret")
	return oms

def get_dc_details():
	l = frappe.get_single("FG Item Settings")
	return {
		"url": l.dc_grn_url,
		"api_key": l.dc_grn_api_key,
		"api_secret": l.get_password("dc_grn_api_secret"),
	}

def make_post_request(data, oms_url, oms_endpoint, oms_api_key, oms_api_secret):
	url = oms_url + oms_endpoint
	headers = {
		"Content-Type": "application/json",
		"Authorization": "token " + oms_api_key + ":" + oms_api_secret
	}
	try:
		response = requests.post(url, json=data, headers=headers)
		if response.status_code == 200:
			response = response.json()
			if 'message' in response:
				return response['message']
			return response
		else:
			return {
				"error": True,
				"status": response.status_code,
				"message": response.text
			}
	except Exception as e:
		return {
			"error": True,
			"status": "",
			"message": e.__str__()
		}
	
def make_get_request(params, oms_url, oms_endpoint, oms_api_key, oms_api_secret):
	url = oms_url + oms_endpoint
	headers = {
		"Content-Type": "application/json",
		"Authorization": "token " + oms_api_key + ":" + oms_api_secret
	}
	try:
		response = requests.get(url, headers=headers, params=params)
		if response.status_code == 200:
			return response.json()
		else:
			return {
				"error": True,
				"status": response.status_code,
				"message": response.text
			}
	except Exception as e:
		return {
			"error": True,
			"status": "",
			"message": e.__str__()
		}