import frappe


def execute():
    frappe.db.sql("""
        UPDATE `tabItem BOM` ib
        INNER JOIN `tabItem` it ON it.name = ib.item
        SET ib.uom = it.default_unit_of_measure
        WHERE (ib.uom IS NULL OR ib.uom = '')
          AND it.default_unit_of_measure IS NOT NULL
          AND it.default_unit_of_measure != ''
    """)

    frappe.db.sql("""
        UPDATE `tabItem BOM Attribute Mapping` m
        INNER JOIN `tabItem` it ON it.name = m.bom_item
        SET m.bom_uom = it.default_unit_of_measure
        WHERE (m.bom_uom IS NULL OR m.bom_uom = '')
          AND it.default_unit_of_measure IS NOT NULL
          AND it.default_unit_of_measure != ''
    """)

    frappe.db.commit()
