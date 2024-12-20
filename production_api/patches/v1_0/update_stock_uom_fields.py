import frappe

def execute():
    frappe.db.sql(
        """update `tabStock Entry Detail` 
        set stock_qty = qty, stock_uom = uom, conversion_factor = 1, stock_uom_rate = rate, amount = qty * rate 
        where 1 = 1;"""
    )

    frappe.db.sql(
        """update `tabStock Reconciliation Item` 
        set stock_qty = qty, stock_uom = uom, conversion_factor = 1, stock_uom_rate = rate, amount = qty * rate 
        where 1 = 1;"""
    )

    frappe.db.sql(
        """update `tabLot Transfer Item` 
        set stock_qty = qty, stock_uom = uom, conversion_factor = 1, stock_uom_rate = rate, amount = qty * rate 
        where 1 = 1;"""
    )

    frappe.db.sql(
        """update `tabGoods Received Note Item` 
        set stock_qty = quantity, stock_uom = uom, conversion_factor = 1, stock_uom_rate = rate, amount = quantity * rate 
        where 1 = 1;"""
    )