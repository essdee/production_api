import frappe


ROLE_NAME = "DocType Reader"
BATCH_SIZE = 100


def setup_doctype_reader_permissions():
	"""Ensure the DocType Reader role exists and has access to role-restricted reports.

	Doctype-level read access is granted at runtime by the has_permission /
	get_role_permissions monkey-patches in frappe_tools.permissions, which
	already include "DocType Reader" in READ_ONLY_ROLES. We deliberately
	write no DocPerm rows here — those get wiped by bench migrate and by
	"Restore Original Permissions".

	Reports use a separate 'Has Role' child table that survives restores, so
	we still need to add DocType Reader to reports that have role restrictions.

	desk_access is set to 1 so the holder can log into the desk and browse,
	which is the only behavioural difference from the AI Bot role.
	"""
	ensure_role_exists()
	setup_report_permissions()


def setup_report_permissions():
	"""Add DocType Reader to the Has Role table of every report that has role restrictions.

	Reports in Frappe use a separate access control via the 'Has Role' child
	table. If a report has roles listed, the user must hold one of those roles
	— even if they have 'report' permission on the underlying doctype. Reports
	with no roles are accessible to everyone, so those are skipped.
	"""
	existing = set(
		frappe.get_all(
			"Has Role",
			filters={"parenttype": "Report", "role": ROLE_NAME},
			pluck="parent",
		)
	)

	all_report_roles = frappe.get_all(
		"Has Role",
		filters={"parenttype": "Report"},
		fields=["parent"],
		group_by="parent",
		pluck="parent",
	)
	reports_needing_access = set(all_report_roles) - existing

	count = 0
	for report_name in reports_needing_access:
		doc = frappe.new_doc("Has Role")
		doc.parent = report_name
		doc.parenttype = "Report"
		doc.parentfield = "roles"
		doc.role = ROLE_NAME
		doc.db_insert()

		count += 1
		if count % BATCH_SIZE == 0:
			frappe.db.commit()

	if count:
		frappe.db.commit()
		frappe.clear_cache()


def ensure_role_exists():
	"""Create the DocType Reader role if it doesn't exist; ensure desk_access=1."""
	if frappe.db.exists("Role", ROLE_NAME):
		role = frappe.get_doc("Role", ROLE_NAME)
		if not role.desk_access:
			role.desk_access = 1
			role.save(ignore_permissions=True)
			frappe.db.commit()
		return
	role = frappe.new_doc("Role")
	role.role_name = ROLE_NAME
	role.desk_access = 1
	role.insert(ignore_permissions=True)
	frappe.db.commit()
