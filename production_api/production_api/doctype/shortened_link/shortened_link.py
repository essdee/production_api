# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import utils, _
from frappe.translate import print_language
import json
import requests


class ShortenedLink(Document):
	def is_expired(self):
		if not self.link_expiry:
			return False
		if utils.get_datetime() < self.link_expiry:
			return False
		return True
	
	def redirect(self):
		if self.is_expired():
			frappe.respond_as_web_page(
				_("Link Expired"),
				_("The resource you are looking for is not available"),
				http_status_code=410,
				indicator_color="red",
			)
			return
			# raise frappe.exceptions.LinkExpired()
		if self.type == "Print PDF":
			self.download_document_pdf()
		elif self.type == "Link":
			self.redirect_link()
	
	def download_document_pdf(self):
		from frappe.utils.pdf import get_pdf
		html = get_print_pdf_via_api({
			"doctype": self.document_type,
			"docname": self.document_linked,
		})
		if html:
			pdf = get_pdf(html)
			frappe.local.response.filename = "{name}.pdf".format(
				name=self.document_linked.replace(" ", "-").replace("/", "-")
			)
			frappe.local.response.filecontent = pdf
			frappe.local.response.type = "pdf"

	def redirect_link(self):
		frappe.response.type = "redirect"
		frappe.response.location = self.link

def get_print_pdf_via_api(args):
	host = '127.0.0.1'
	site_name = frappe.local.site
	port = frappe.get_site_config().webserver_port
	api_key = frappe.db.get_value("User", "Administrator", "api_key")
	api_secret = frappe.utils.password.get_decrypted_password("User", "Administrator", fieldname="api_secret")
	headers = {
		'Accept': 'application/json',
		'Authorization': f'token {api_key}:{api_secret}',
		'Content-Type': 'application/json',
		'X-Forwarded-For':'127.0.0.1',
		'X-Forwarded-Proto': 'https://',
		'X-Frappe-Site-Name': site_name,
		'Host': site_name
	}
	url = f'http://{host}:{port}/api/method/production_api.production_api.doctype.shortened_link.shortened_link.get_print_pdf'
	payload = {
		'doctype': args["doctype"],
		'docname': args["docname"],
		'print_format': args["print_format"] if "print_format" in args else None
	}
	response = json.loads(requests.request("POST", url, headers=headers, data = json.dumps(payload)).text.encode('utf8'))['message']
	return response

@frappe.whitelist()
def get_print_pdf(doctype, docname, print_format = None):
	doc = frappe.get_doc(doctype, docname)
	default_letterhead = None
	letterheads = frappe.get_all(
		doctype = "Letter Head", 
		filters = { "disabled": 0 },
		fields = ["name", "is_default"]
	)
	for letterhead in letterheads:
		if (letterhead["is_default"]): 
			default_letterhead = letterhead["name"]
	with print_language(None):
		html = frappe.get_print(
			doctype, docname, print_format, doc=doc, letterhead=default_letterhead, no_letterhead=0
		)
		if isinstance(html, bytes):
			html = html.decode("utf-8")
		return html

def create_print_sl(doctype, docname):
	sl = frappe.get_doc({
		"doctype": "Shortened Link",
		"type": "Print PDF",
		"document_type": doctype,
		"document_linked": docname,
	})
	expires_in = frappe.db.get_single_value("MRP Settings", "link_expiry_days") or 14
	sl.link_expiry = utils.add_days(utils.now(), expires_in)
	sl.insert()
	return sl.name

def get_short_link(doctype, docname):
	if not doctype and not docname:
		return None
	
	sl_name = create_print_sl(doctype, docname)
	shortened_url_domain = frappe.get_doc("MRP Settings").shortned_url_domain
	link = f"{shortened_url_domain}{sl_name}"
	return link

	

