import frappe

def execute():
    frappe.db.sql(
        """
            UPDATE `tabDelivery Challan Item` SET stock_qty = delivered_quantity, stock_uom = uom, 
            conversion_factor = 1 WHERE stock_uom IS NULL
        """
    )
    frappe.db.sql(
        """
            UPDATE `tabGoods Received Note Item` as t1 JOIN `tabGoods Received Note` as t2  
            ON t1.parent = t2.name SET t1.stock_qty = t1.quantity, 
            t1.stock_uom = t1.uom, t1.conversion_factor = 1 
            WHERE t1.stock_uom IS NULL and t2.against = 'Work Order'
        """
    )