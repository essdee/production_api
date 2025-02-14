import frappe

def execute():
    frappe.reload_doctype("Cutting Marker")
    frappe.reload_doctype("Cutting Marker Ratio")
    frappe.reload_doctype("Cutting LaySheet")
    cm_list = frappe.get_all("Cutting Marker", pluck="name")
    print(len(cm_list))
    for cm in cm_list:
        part_list = frappe.db.sql(
            f"""
                Select part from `tabCutting Marker Part` where parent = '{cm}' and docstatus = 0 
            """, as_dict=True
        )
        if len(part_list) > 0:
            items = []
            cm_doc = frappe.get_doc("Cutting Marker", cm)
            panels = []
            for marker in cm_doc.cutting_marker_ratios:
                for part in part_list:
                    if part.part not in panels:
                        panels.append(part.part)
                    items.append({
                        "size":marker.size,
                        "panel":part.part,
                        "ratio":marker.ratio
                    }) 
            cm_doc.set("cutting_marker_ratios", items)
            cm_doc.set("selected_type","Machine")
            cm_doc.set("calculated_parts",",".join(panels))
            cm_doc.submit()

            cls_list = frappe.get_list("Cutting LaySheet",filters={"cutting_marker":cm}, pluck="name")
            
            for cls in cls_list:
                cls_doc = frappe.get_doc("Cutting LaySheet", cls)
                cls_doc.set("cutting_marker_ratios", items)
                cls_doc.set("selected_type","Machine")
                cls_doc.set("calculated_parts",",".join(panels))
                cls_doc.save()
