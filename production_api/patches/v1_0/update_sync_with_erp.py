import frappe

def execute():
    frappe.db.sql(
        """
            UPDATE `tabItem Variant` t1
            JOIN `tabItem` t2 ON t1.item = t2.name
            SET t1.sync_with_erp = 1 
            WHERE t2.dependent_attribute IS NULL 
            OR t2.dependent_attribute = ''
        """
    )
    variants = frappe.db.sql(
        """
            SELECT t1.name
            FROM `tabItem Variant` t1
            JOIN `tabItem` t2 ON t1.item = t2.name
            WHERE t2.dependent_attribute IS NOT NULL
            AND t2.dependent_attribute != ''
        """
    )

    stich_attr = frappe.db.get_single_value("IPD Settings", "default_stitching_attribute")
    for variant in variants:
        attributes = frappe.db.sql(
            """
            SELECT name, attribute FROM `tabItem Variant Attribute` WHERE parent = %s
            AND attribute = %s
        """,
        (variant[0], stich_attr)
        )
        if not attributes:
            frappe.db.sql(
                """
                    UPDATE `tabItem Variant` SET sync_with_erp = 1 WHERE name = %s
                """,
                (variant[0],)
            )
            print(attributes)
