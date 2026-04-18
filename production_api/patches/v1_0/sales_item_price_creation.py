import frappe


def execute():

	Fg = frappe.get_all("FG Item Master", filters={
						"is_scheme": 0}, pluck="item")
	if not Fg:
		return

	variant = frappe.get_all("Item Variant", filters={
							 "item": ["in", Fg]}, pluck="name")
	if not variant:
		return

	primary_att = frappe.get_single_value(
		"IPD Settings", "default_primary_attribute")

	iv_name = []
	for v in variant:
		v_doc = frappe.get_doc("Item Variant", v)
		att_v = set()
		if primary_att:
			att_v.add(primary_att)
		dep_att = frappe.get_value("Item", v_doc.item, "dependent_attribute")
		if dep_att:
			att_v.add(dep_att)

		iv_att = {r.attribute for r in v_doc.attributes}
		if att_v == iv_att:
			iv_name.append(v_doc.name)

	exist = frappe.get_all("Sales Item Price",
						   filters={"item_variant": ["in", iv_name]}, pluck="item_variant")
	exist1 = set(exist)

	new_iv = [v for v in iv_name if v not in exist1]

	for i in new_iv:
		frappe.get_doc({
			"doctype": "Sales Item Price",
			"item_variant": i,
			"rate": 0,
			"retail_rate": 0,
			"mrp_rate": 0
		}).insert(ignore_permissions=True)
