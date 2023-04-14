import frappe
from production_api.production_api.doctype.supplier.supplier import Supplier

@frappe.whitelist()
def send_notification(
	doctype: str,
	docname :str,
	event: str = None,
	channels: str | list[str]=['Email', 'SMS'],
	supplier_key: str='supplier',
	is_auto_send: bool=False
):
	if not channels:
		return
	if isinstance(channels, str):
		if channels.startswith("["):
			channels = frappe.parse_json(channels)
		else:
			channels = [channels]
	if is_auto_send:
		mrp_settings = frappe.get_doc("MRP Settings")
		if not mrp_settings.auto_send_notifications:
			return
		if not any([(doctype == row.doc_type and row.enabled) for row in mrp_settings.auto_send_notifications]):
			return
	doc = frappe.get_doc(doctype, docname)
	if not event:
		if doc.docstatus == 1:
			event = 'Submit'
		elif doc.docstatus == 2:
			event = 'Cancel'
		elif doc.docstatus == 0:
			event = 'Save'
	
	# get supplier from doc
	supplier_name = doc.get(supplier_key)
	if not supplier_name:
		return
	supplier: Supplier = frappe.get_doc("Supplier", supplier_name)
	supplier.send_notification(doctype, docname, channels, event)

def validate_communication(doc, method=None):
	if doc.communication_medium == "SMS":
		contacts = []
		contacts = get_contacts_with_phone_number([doc.recipients])
		from frappe.core.doctype.communication.communication import add_contact_links_to_communication
		for contact_name in contacts:
			doc.add_link("Contact", contact_name)
			# link contact's dynamic links to communication
			add_contact_links_to_communication(doc, contact_name)

def get_contacts_with_phone_number(phone_numbers: list[str]) -> list[str]:
	from frappe.contacts.doctype.contact.contact import get_contact_with_phone_number
	contacts = []
	for phone in phone_numbers:
		contact_name = get_contact_with_phone_number(phone)
		if contact_name:
			contacts.append(contact_name)
	return contacts