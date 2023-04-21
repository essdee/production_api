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

@frappe.whitelist()
def get_notification_message(
	doctype: str,
	docname :str,
	event: str = None,
	channel: str = 'Copy Message',
):
	doc = frappe.get_doc(doctype, docname)
	if not event:
		if doc.docstatus == 1:
			event = 'Submit'
		elif doc.docstatus == 2:
			event = 'Cancel'
		elif doc.docstatus == 0:
			event = 'Save'

	filters = {
		"document_type": doctype,
		"channel": channel,
		"event": event,
		"enabled": 1
	}
	notification_templates = frappe.get_all("Notification Template", filters=filters)
	if not notification_templates:
		frappe.msgprint("No Notification Template Found")
		return
	template = frappe.get_doc("Notification Template", notification_templates[0].name)
	message = template.get_message(docname=docname)
	return message


@frappe.whitelist(allow_guest=True)
def parse_short_link(hash=None):
	if hash is None:
		raise frappe.exceptions.DoesNotExistError("Not Valid")
	
	sl = frappe.get_doc("Shortened Link", hash)
	sl.link_views = sl.link_views + 1
	sl.save(ignore_permissions=True)
	frappe.db.commit()
	try:
		sl.redirect()
	except:
		raise

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

def send_automatic_notification(doc, method=None):
	# check if doc is present in 
	event = None
	if method == 'on_submit':
		event = 'Submit'
	elif method == 'on_cancel':
		event = 'Cancel'
	elif method == 'after_insert' and doc.is_new():
		event = 'Save'
	if event:
		send_notification(doc.doctype, doc.name, event, is_auto_send=True)

def parse_string_for_SMS(string: str, variable_count=1, max_variable_length=30, end_with:str="...") -> str:
	"""
	:param string: string to be parsed
	:param variable_count: Total Number of simultaneous variables
	:param max_variable_length: Maximum length of a variable
	Based on Indian SMS standards a variable can have a maximum of 30 characters
	and if there are multiple variables It is multiplied by the number of variables
	:param end_with: string to be added at the end of the string if it is truncated
	"""
	if len(string) <= max_variable_length * variable_count:
		return string
	else:
		return string[:max_variable_length * variable_count - len(end_with)] + end_with