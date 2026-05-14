import frappe
from frappe.model.document import Document


class WODebit(Document):
	def validate(self):
		if not self.inspection and not self.debit_no:
			frappe.throw("Debit No is required.")
		if self.inspection and not self.debit_document:
			frappe.throw("Debit Document is required.")

	def before_submit(self):
		merch_role = frappe.db.get_single_value("MRP Settings", "merchandising_manager_role")
		if merch_role and merch_role in frappe.get_roles(frappe.session.user):
			self.status = "Approved"
			self.approved_by = frappe.session.user
		else:
			self.status = "Debit Requested"


@frappe.whitelist()
def approve_debit(name):
	merch_role = frappe.db.get_single_value("MRP Settings", "merchandising_manager_role")
	if not merch_role or merch_role not in frappe.get_roles(frappe.session.user):
		frappe.throw("You do not have permission to approve debits.")

	doc = frappe.get_doc("WO Debit", name)
	if doc.docstatus != 1:
		frappe.throw("WO Debit must be submitted before approval.")
	if doc.status != "Debit Requested":
		frappe.throw("WO Debit is already approved.")

	doc.status = "Approved"
	doc.approved_by = frappe.session.user
	doc.save(ignore_permissions=True)
	frappe.db.commit()
