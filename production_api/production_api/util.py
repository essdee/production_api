import frappe
from frappe.core.doctype.sms_settings.sms_settings import send_sms

def send_submitted_doc(doc):
	shortned_link = frappe.new_doc("Shortened Link")
	shortned_link.document_type = "Purchase Order"
	shortned_link.document_linked = doc.name
	shortned_link.insert()
	shortned_url_domain = frappe.get_doc("MRP Settings").shortned_url_domain
	link = f"{shortned_url_domain}/{shortned_link.name}"
	# Fetch contact doc
	# If contact doc has phone number and site has SMS settings set send sms using send_sms()

	msg = f"""Dear {doc.contact_person} Bill No: {doc.name} Dt: {doc.name} L.R.No: {doc.name} Cartons dispatched: {doc.name} CARTONS. Total: {doc.name} Thank you.
	Increase the ease of doing business by downloading our app {link}
	- Essdee"""
	print(msg)
	if doc.contact_mobile:
		send_sms([doc.contact_mobile], msg)
	# TODO If contact doc has email send email with PDF attachment using frappe.sendmail() 