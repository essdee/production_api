import frappe

def execute():
    frappe.db.sql(
		"""
			UPDATE `tabCutting LaySheet Detail` SET effective_bits = CASE
				WHEN fabric_type = 'Tubler' THEN no_of_bits * 2
				WHEN fabric_type = 'Open Width' THEN no_of_bits
				ELSE effective_bits
			END;	 
		"""
	)