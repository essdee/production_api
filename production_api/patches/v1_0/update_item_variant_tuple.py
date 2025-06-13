import frappe

def execute():
    item_variant_list = frappe.get_all("Item Variant", pluck="name")
    for variant in item_variant_list:
        doc = frappe.get_doc("Item Variant", variant)
        d = {}
        for attribute in doc.attributes:
            d[attribute.attribute] = attribute.attribute_value
        tup = tuple(sorted(d.items()))    
        if tup:
            doc.item_tuple_attribute = str(tup)
            doc.save()
