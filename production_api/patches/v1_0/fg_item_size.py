import frappe

def execute():
    """
    Update all FG Item Size with the comma separated size in available_sizes
    """
    for item in frappe.get_all("FG Item Master"):
        doc = frappe.get_doc("FG Item Master", item.name)
        if doc.available_sizes:
            sizes = [{'attribute_value': size} for size in doc.available_sizes.split(",")]
            doc.set("sizes", sizes)
            doc.save()
