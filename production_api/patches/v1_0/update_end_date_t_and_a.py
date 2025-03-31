import frappe

def execute():
    frappe.db.sql(
        """
            UPDATE `tabTime and Action` t1
            JOIN (
                SELECT t2.parent, t2.rescheduled_date
                FROM `tabTime and Action Detail` t2
                WHERE t2.idx = (
                    SELECT MAX(idx) 
                    FROM `tabTime and Action Detail` 
                    WHERE parent = t2.parent
                )
            ) latest ON t1.name = latest.parent
            SET t1.end_date = latest.rescheduled_date;
        """
    )