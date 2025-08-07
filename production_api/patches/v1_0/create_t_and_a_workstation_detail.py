import frappe

def execute():
    tAndA_list = frappe.get_all("Time and Action", pluck="name")
    for tAndA in tAndA_list:
        doc = frappe.get_doc("Time and Action", tAndA)
        child_table_data = []
        for row in doc.details:
            if row.work_station:
                child_table_data.append({
                    "parent_link_value": row.name,
                    "work_station": row.work_station,
                    "rescheduled_date": row.rescheduled_date,
                    "actual_date": row.actual_date,
                    "date_diff": row.date_diff,
                    "reason": row.reason,
                    "performance": row.performance,
                })
        doc.set("time_and_action_work_station_details", child_table_data)
        doc.save()        