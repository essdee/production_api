import frappe

def execute():
    action_master_list = frappe.get_all("Action Master", pluck="name")
    for action_master in action_master_list:
        doc = frappe.get_doc("Action Master", action_master)
        d = []
        action = None
        for row in doc.details:
            if row.idx == 1:
                action = row.action
                continue
            d.append({
                "action": row.action,
                "dependent_action": action
            })

            action = row.action
        doc.set("action_master_dependent_details", d)
        doc.disable = 1
        doc.save()    

    TandAList = frappe.get_all("Time and Action", pluck="name")
    for TandA in TandAList:
        doc = frappe.get_doc("Time and Action", TandA)    
        d = []
        action = None
        date = None
        for row in doc.details:
            if row.idx == 1:
                action = row.action
                date = row.actual_date
                continue
            d.append({
                "action": row.action,
                "dependent_action": action,
                "dependent_action_date": date,
            })

            action = row.action
            date = row.actual_date
        doc.set("dependent_details", d)
        doc.save()