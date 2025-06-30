import frappe

def execute():
    ipd_list = frappe.get_all("Item Production Detail", pluck="name")

    for ipd in ipd_list:
        ipd_doc = frappe.get_doc("Item Production Detail", ipd)
        for row in ipd_doc.item_bom:
            if row.based_on_attribute_mapping:
                frappe.db.sql(
                    """
                        UPDATE `tabItem BOM Attribute Mapping Value` SET quantity = %(qty)s WHERE parent = %(parent)s
                    """, {
                        "qty": row.qty_of_bom_item,
                        "parent": row.attribute_mapping,
                    }
                )