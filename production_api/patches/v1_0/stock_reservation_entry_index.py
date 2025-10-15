import frappe

def execute():
    try:
        frappe.db.sql("""
            ALTER TABLE `tabStock Reservation Entry`  
                DROP INDEX warehouse_lot_item_code_received_type_status_index,   
                DROP INDEX warehouse_lot_item_code_received_type_index,   
                DROP INDEX voucher_type_voucher_no_status_index;
        """)
    except Exception as e:
        print(e)
    frappe.db.sql("""
        OPTIMIZE TABLE `tabStock Reservation Entry`;
    """)