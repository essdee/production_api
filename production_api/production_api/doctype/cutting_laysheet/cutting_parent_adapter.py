# Adapter module for Cutting Marker / LaySheet to work with either Cutting Plan or Cutting Order
import frappe
from production_api.essdee_production.doctype.item_production_detail.item_production_detail import get_ipd_primary_values


def get_parent_ref(doc):
	"""Returns (parent_doctype, parent_name) from a Marker or LaySheet doc."""
	if doc.cutting_plan:
		return ("Cutting Plan", doc.cutting_plan)
	elif doc.cutting_order:
		return ("Cutting Order", doc.cutting_order)
	frappe.throw("Either Cutting Plan or Cutting Order is required")


def get_detail_doc(parent_dt, parent_name):
	"""Returns IPD doc (for CP) or COD doc (for CO).
	Both have: packing_attribute, set_item_attribute, stiching_attribute,
	is_set_item, stiching_item_details (child table).
	"""
	if parent_dt == "Cutting Plan":
		pd = frappe.get_value("Cutting Plan", parent_name, "production_detail")
		return frappe.get_cached_doc("Item Production Detail", pd)
	else:
		cod_name = frappe.get_value("Cutting Order", parent_name, "cutting_order_detail")
		return frappe.get_cached_doc("Cutting Order Detail", cod_name)


def validate_parent_status(parent_dt, parent_name):
	"""Validates parent is submitted and ready for cutting."""
	if parent_dt == "Cutting Plan":
		status, docstatus = frappe.get_value("Cutting Plan", parent_name, ["cp_status", "docstatus"])
		if docstatus == 0:
			frappe.throw("Cutting Plan was not Submitted")
		if status == 'Planned':
			frappe.throw("Cloths Not Received in Cutting Plan")
	else:
		docstatus = frappe.get_value("Cutting Order", parent_name, "docstatus")
		if docstatus != 1:
			frappe.throw("Cutting Order was not Submitted")


def get_panels(parent_dt, parent_name):
	"""Returns panel list from IPD (via CP) or COD (via CO)."""
	detail_doc = get_detail_doc(parent_dt, parent_name)
	return [{"part": row.stiching_attribute_value} for row in detail_doc.stiching_item_details]


def get_primary_sizes(parent_dt, parent_name):
	"""Returns size list."""
	if parent_dt == "Cutting Plan":
		pd = frappe.get_value("Cutting Plan", parent_name, "production_detail")
		return get_ipd_primary_values(pd)
	else:
		cod_name = frappe.get_value("Cutting Order", parent_name, "cutting_order_detail")
		cod = frappe.get_cached_doc("Cutting Order Detail", cod_name)
		for attr_row in cod.item_attributes:
			if attr_row.attribute == cod.primary_attribute and attr_row.mapping:
				mapping_doc = frappe.get_cached_doc("Item Item Attribute Mapping", attr_row.mapping)
				return [v.attribute_value for v in mapping_doc.values]
		return []


def get_parent_context(parent_dt, parent_name):
	"""Returns a dict with fields that downstream code needs."""
	if parent_dt == "Cutting Plan":
		doc = frappe.get_doc("Cutting Plan", parent_name)
		return {
			"parent_dt": parent_dt,
			"parent_name": parent_name,
			"item": doc.item,
			"lot": doc.lot,
			"work_order": doc.work_order,
			"lay_no": doc.lay_no,
			"maximum_no_of_plys": doc.maximum_no_of_plys,
			"maximum_allow_percent": doc.maximum_allow_percent,
			"is_manual_entry": doc.is_manual_entry,
			"version": doc.version,
			"production_detail": doc.production_detail,
		}
	else:
		doc = frappe.get_doc("Cutting Order", parent_name)
		cod = frappe.get_cached_doc("Cutting Order Detail", doc.cutting_order_detail)
		return {
			"parent_dt": parent_dt,
			"parent_name": parent_name,
			"item": doc.item,
			"lot": None,
			"work_order": None,
			"lay_no": doc.lay_no,
			"maximum_no_of_plys": doc.maximum_no_of_plys,
			"maximum_allow_percent": doc.maximum_allow_percent,
			"is_manual_entry": 0,
			"version": "V3",
			"production_detail": doc.cutting_order_detail,
		}


def increment_lay_no(parent_dt, parent_name, new_lay_no):
	"""Updates lay_no on CP or CO."""
	if parent_dt == "Cutting Plan":
		doc = frappe.get_doc("Cutting Plan", parent_name)
		doc.lay_no = new_lay_no
		doc.flags.ignore_permissions = 1
		doc.save(ignore_permissions=True)
	else:
		frappe.db.set_value("Cutting Order", parent_name, "lay_no", new_lay_no, update_modified=False)


def update_parent_status_on_first_lay(parent_dt, parent_name):
	"""Sets status to 'Cutting In Progress' on first laysheet."""
	if parent_dt == "Cutting Plan":
		frappe.db.sql(
			f"""
				UPDATE `tabCutting Plan` SET cp_status = 'Cutting In Progress'
				WHERE name = {frappe.db.escape(parent_name)}
			"""
		)
	else:
		frappe.db.set_value("Cutting Order", parent_name, "co_status", "Cutting In Progress", update_modified=False)


def has_cloth_tracking(parent_dt):
	"""Returns True for CP (has cutting_plan_cloth_details), False for CO."""
	return parent_dt == "Cutting Plan"


def has_work_order(parent_dt, parent_name=None):
	"""Returns True for CP (if work_order exists), False for CO."""
	if parent_dt == "Cutting Order":
		return False
	if parent_name:
		wo = frappe.get_value("Cutting Plan", parent_name, "work_order")
		return bool(wo)
	return True


def is_parent_completed(parent_dt, parent_name):
	"""Check if parent's status indicates completion."""
	if parent_dt == "Cutting Plan":
		status = frappe.get_value("Cutting Plan", parent_name, "cp_status")
		return status == "Completed"
	else:
		status = frappe.get_value("Cutting Order", parent_name, "co_status")
		return status == "Completed"


def get_completed_incomplete_json(parent_dt, parent_name):
	"""Returns (completed_items_json, incomplete_items_json, version) from parent."""
	if parent_dt == "Cutting Plan":
		return frappe.get_value(
			"Cutting Plan", parent_name,
			["production_detail", "incomplete_items_json", "completed_items_json", "version"]
		)
	else:
		cod_name, incomplete, completed = frappe.get_value(
			"Cutting Order", parent_name,
			["cutting_order_detail", "incomplete_items_json", "completed_items_json"]
		)
		return (cod_name, incomplete, completed, "V3")


def save_completed_incomplete_json(parent_dt, parent_name, completed_items, incomplete_items):
	"""Saves completed/incomplete JSON back to the parent doc."""
	if parent_dt == "Cutting Plan":
		cp_doc = frappe.get_doc("Cutting Plan", parent_name)
		cp_doc.completed_items_json = completed_items
		cp_doc.incomplete_items_json = incomplete_items
		cp_doc.save(ignore_permissions=True)
		return cp_doc
	else:
		frappe.db.set_value("Cutting Order", parent_name, {
			"completed_items_json": completed_items if isinstance(completed_items, str) else frappe.as_json(completed_items),
			"incomplete_items_json": incomplete_items if isinstance(incomplete_items, str) else frappe.as_json(incomplete_items),
		}, update_modified=False)
		co_doc = frappe.get_doc("Cutting Order", parent_name)
		co_doc.run_method("on_update_after_submit")
		return co_doc


def get_marker_parent_field(parent_dt):
	"""Returns the field name on Cutting Marker that stores the parent link."""
	return "cutting_plan" if parent_dt == "Cutting Plan" else "cutting_order"
