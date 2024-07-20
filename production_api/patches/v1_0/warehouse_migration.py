import frappe

def execute():
    # update Stock Reconciliation default_warehouse
    frappe.db.sql(
        """
            UPDATE `tabStock Reconciliation` t
            JOIN tabSupplier j ON t.default_warehouse = j.name
            SET t.default_warehouse = j.default_warehouse;
        """
	)
    # update Stock Reconciliation Item warehouse
    frappe.db.sql(
        """
            UPDATE `tabStock Reconciliation Item` t
            JOIN tabSupplier j ON t.warehouse = j.name
            SET t.warehouse = j.default_warehouse;
        """
	)
    # update Stock Entry from_warehouse
    frappe.db.sql(
        """
            UPDATE `tabStock Entry` t
            JOIN tabSupplier j ON t.from_warehouse = j.name
            SET t.from_warehouse = j.default_warehouse;
        """
	)
    # update Stock Entry to_warehouse
    frappe.db.sql(
        """
            UPDATE `tabStock Entry` t
            JOIN tabSupplier j ON t.to_warehouse = j.name
            SET t.to_warehouse = j.default_warehouse;
        """
	)
    # update Stock Ledger Entry warehouse
    frappe.db.sql(
        """
            UPDATE `tabStock Ledger Entry` t
            JOIN tabSupplier j ON t.warehouse = j.name
            SET t.warehouse = j.default_warehouse;
        """
	)
    # update Stock Settings transit_warehouse
    frappe.db.sql(
        """
            UPDATE `tabSingles` t
            JOIN tabSupplier j ON t.field = j.transit_warehouse and t.doctype = `Stock Settings`
            SET t.value = j.default_warehouse;
        """
	)
    # update Lot Transfer Item warehouse
    frappe.db.sql(
        """
            UPDATE `tabLot Transfer Item` t
            JOIN tabSupplier j ON t.warehouse = j.name
            SET t.warehouse = j.default_warehouse;
        """
	)