import frappe

def execute():
    items = frappe.db.sql(
        """
            SELECT name FROM `tabItem` WHERE dependent_attribute IS NOT NULL AND dependent_attribute != ''
        """, as_dict=True
    )
    doc = frappe.new_doc("Item Attribute Value")
    doc.attribute_name = "Stage"
    doc.attribute_value = "Loose Piece"
    doc.save()

    for item in items:
        item = item['name']
        item_doc = frappe.get_doc("Item", item)
        mapping = None
        for row in item_doc.attributes:
            if row.attribute == item_doc.dependent_attribute:
                mapping = row.mapping
                break
        map_doc = frappe.get_doc("Item Item Attribute Mapping", mapping)
        map_doc.append("values", {
            "attribute_value": "Loose Piece",
        })
        map_doc.save()

        dependent_doc = frappe.get_doc("Item Dependent Attribute Mapping", item_doc.dependent_attribute_mapping)
        dependent_doc.append("mapping", {
            "dependent_attribute_value": "Loose Piece",
            "depending_attribute": item_doc.primary_attribute,
        })
        dependent_doc.append("details", {
            "attribute_value": "Loose Piece",
            "uom": item_doc.default_unit_of_measure,
            "display_name": "Loose Piece",
        })
        dependent_doc.save()
