import frappe

def execute():
    make_over_done_reservation_fix()

def make_over_done_reservation_fix():

    query = """
        SELECT name FROM `tabStock Reservation Entry` WHERE status='Reserved' AND delivered_qty > 0 AND delivered_qty > reserved_qty
    """
    sres = frappe.db.sql(query, as_dict=True)

    for i in sres:
        sre = frappe.get_doc("Stock Reservation Entry", i['name'])
        sre.delivered_qty = sre.reserved_qty
        sre.db_update()
        sre.update_status()
        sre.update_reserved_stock_in_bin()
