import frappe
def execute():
	frappe.db.sql("""
		UPDATE `tabGoods Received Note`
		SET `actual_date` = `posting_date`
		WHERE `posting_date` IS NOT NULL
			AND `actual_date` IS NULL
	""")

	frappe.db.sql("""
		UPDATE `tabDelivery Challan`
		SET `actual_date` = `posting_date`
		WHERE `posting_date` IS NOT NULL
			AND `actual_date` IS NULL
	""")
