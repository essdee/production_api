import frappe
from frappe.utils import getdate, add_months, nowdate
from production_api.utils import update_if_string_instance

def execute():
    draft_lot_list = ["C0925-71", "F0925-23", "F0925-23/1", "F0925-23/2", "F0925-23/3", "C0925-67"]
    lot_list = tuple(draft_lot_list)
    query = f"""UPDATE `tabCutting Plan` SET status = 'Draft' WHERE lot IN {lot_list} """
    frappe.db.sql(query)
    cp_list = frappe.get_all("Cutting Plan", filters={
        "lot": ["not in", draft_lot_list]
    },pluck="name")
    close_cp_date = getdate(add_months(nowdate(), -2))
    for cp in cp_list:
        status, work_order, creation = frappe.get_value("Cutting Plan", cp, ["status", "work_order", "creation"])
        creation = getdate(creation)
        if creation < close_cp_date:
            update_cp_docstatus(cp, 'Completed', old=True)
        elif status == 'Completed':
            update_cp_docstatus(cp, 'Completed')
        else:
            status = None
            cp_doc = frappe.get_doc("Cutting Plan", cp)
            completed_json = update_if_string_instance(cp_doc.completed_items_json)
            check = True
            one_colour_completed = False
            for row in completed_json['items']:
                if row['completed']:
                    one_colour_completed = True
                if not row['completed']:
                    check = False
            if check:
                status = 'Completed'
            elif one_colour_completed:
                status = 'Partially Completed'   
            else:     
                cls_list = frappe.get_all("Cutting LaySheet", filters={
                    "cutting_plan": cp
                }, pluck="name")
                if cls_list:
                    status = "Cutting In Progress"
            
            if not status:
                dc_list = frappe.get_all("Delivery Challan", filters={
                    "work_order": cp_doc.work_order,
                    "docstatus": 1,
                }, pluck="name")
                if dc_list:
                    status = 'Ready to Cut'
                else:
                    status = "Planned"
            update_cp_docstatus(cp, status)

def update_cp_docstatus(cp, status, old=False):
    frappe.db.sql(
        f"""
            UPDATE `tabCutting Plan` SET docstatus = 1, status = {frappe.db.escape(status)} ,
            open_status = 'Open' WHERE name = {frappe.db.escape(cp)}
        """
    )
    frappe.db.sql(
        f"""
            UPDATE `tabLot Order Detail` SET docstatus = 1 WHERE parent = {frappe.db.escape(cp)}
        """
    )
    frappe.db.sql(
        f"""
            UPDATE `tabCutting Plan Cloth Detail` SET docstatus = 1 WHERE parent = {frappe.db.escape(cp)}
        """
    )

    if old:
        frappe.db.sql(
            f"""
                UPDATE `tabCutting Plan` SET open_status = 'Closed' WHERE name = {frappe.db.escape(cp)}
            """
        )