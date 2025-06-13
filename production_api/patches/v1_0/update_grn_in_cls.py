import frappe

def execute():
    frappe.db.sql(
        """
            UPDATE `tabCutting LaySheet` cl
            JOIN (
                SELECT name, cutting_laysheet FROM `tabGoods Received Note` WHERE docstatus = 1 
                AND against = 'Work Order' AND cutting_laysheet IS NOT NULL
            ) t1
            ON cl.name = t1.cutting_laysheet
            SET cl.goods_received_note = t1.name;
        """
    )