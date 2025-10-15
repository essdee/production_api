import frappe

def execute():
    wo_list = frappe.get_all("Work Order", filters={
        "docstatus": 1,
        "first_dc_date": ['is', 'not set']
    }, pluck="name")

    for wo in wo_list:
        date = frappe.db.sql(
            """
                SELECT max(posting_date) as last_dc_date , min(posting_date) as first_dc_date 
                FROM `tabDelivery Challan` WHERE docstatus = 1 AND work_order = %(wo)s
            """, {
                "wo": wo
            }, as_dict=True
        )
        if date and date[0].get("last_dc_date"):
            frappe.db.sql(
                """
                    UPDATE `tabWork Order` SET first_dc_date = %(first_date)s, last_dc_date = %(last_date)s
                    WHERE name = %(wo)s
                """, {
                    "first_date": date[0]['first_dc_date'],
                    "last_date": date[0]['last_dc_date'],
                    "wo": wo
                }
            )