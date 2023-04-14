# Copyright (c) 2023, Essdee and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import utils, _
from frappe.translate import print_language


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
		doc = frappe.get_doc(self.document_type, self.document_linked)
		language = None
		format = None
		default_letterhead = None
		letterheads = frappe.get_list(
			doctype = "Letter Head", 
			filters = { "disabled": 0 },
			fields = ["name", "is_default"]
		)
		for letterhead in letterheads:
			if (letterhead["is_default"]): 
				default_letterhead = letterhead["name"]
		with print_language(language):
			pdf_file = frappe.get_print(
				self.document_type, self.document_linked, format, doc=doc, as_pdf=True, letterhead=default_letterhead, no_letterhead=0
			)

		frappe.local.response.filename = "{name}.pdf".format(
			name=self.document_linked.replace(" ", "-").replace("/", "-")
		)
		frappe.local.response.filecontent = pdf_file
		frappe.local.response.type = "pdf"

	def redirect_link(self):
		frappe.db.commit()
		frappe.response.type = "redirect"
		frappe.response.location = self.link

@frappe.whitelist(allow_guest=True)
def parse_link(hash=None):
	if hash is None:
		raise frappe.exceptions.DoesNotExistError("Not Valid")
	
	sl = frappe.get_doc("Shortened Link", hash)
	sl.link_views = sl.link_views + 1
	sl.save(ignore_permissions=True)
	try:
		sl.redirect()
	except:
		raise

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

	

