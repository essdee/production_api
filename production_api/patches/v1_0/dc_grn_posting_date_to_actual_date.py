import frappe
def execute():
	grn_doc=frappe.get_all("Goods Received Note",
					filters={"posting_date":("is","set"),"actual_date":("is","not set")},
					fields=["name","posting_date"])
	for x in grn_doc:
		frappe.db.set_value(
			"Goods Received Note",
			x.name,
			"actual_date",
			x.posting_date,
			update_modified=False
		)
		
	dc_doc=frappe.get_all("Delivery Challan",
					filters={"posting_date":("is","set"),"actual_date":("is","not set")},
					fields=["name","posting_date"])
	for x in dc_doc:
		frappe.db.set_value(
			"Delivery Challan",
			x.name,
			"actual_date",
			x.posting_date,
			update_modified=False
		)


