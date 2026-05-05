import frappe

def execute():
    frappe.db.sql(
        """
            DELETE FROM `tabCut Bundle Movement Ledger` WHERE voucher_no = 'CLS-2601-00088'
            AND is_cancelled = 1
        """
    )
    frappe.db.sql(
        """
            UPDATE `tabCut Bundle Movement Ledger` 
            SET quantity_after_transaction = quantity 
            WHERE voucher_no = 'CLS-2601-00088'
        """
    )
