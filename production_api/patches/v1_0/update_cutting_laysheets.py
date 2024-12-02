import frappe
def execute():
    cls_list = frappe.get_all("Cutting LaySheet",pluck="name")
    for cls in cls_list:
        cls_doc = frappe.get_doc("Cutting LaySheet",cls)    
        if cls_doc.printed_time:
            cls_doc.status = "Label Printed"
        elif len(cls_doc.cutting_laysheet_bundles) > 0:
            cls_doc.status = "Bundles Generated"
        elif len(cls_doc.cutting_laysheet_details) > 0:
            cls_doc.status = "Completed"
        else:
            cls_doc.status = "Started"
        
        cls_doc.save()        