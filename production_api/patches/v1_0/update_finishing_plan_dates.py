import frappe
import json

def execute():
    finishing_plans = frappe.get_all("Finishing Plan", fields=["name", "dc_list", "grn_list"])

    for fp in finishing_plans:
        updates = {}

        # finishing_start_date from earliest DC posting_date
        dc_list = fp.dc_list
        if dc_list:
            try:
                dc_dict = json.loads(dc_list) if isinstance(dc_list, str) else dc_list
            except (json.JSONDecodeError, TypeError):
                dc_dict = {}

            if dc_dict:
                dc_names = list(dc_dict.keys())
                dates = frappe.get_all(
                    "Delivery Challan",
                    filters={"name": ["in", dc_names], "docstatus": 1},
                    fields=["posting_date"],
                    pluck="posting_date",
                )
                if dates:
                    updates["finishing_start_date"] = min(dates)

        # finishing_end_date from earliest GRN posting_date (from_finishing, non-return)
        grn_list = fp.grn_list
        if grn_list:
            try:
                grn_dict = json.loads(grn_list) if isinstance(grn_list, str) else grn_list
            except (json.JSONDecodeError, TypeError):
                grn_dict = {}

            if grn_dict:
                grn_names = list(grn_dict.keys())
                dates = frappe.get_all(
                    "Goods Received Note",
                    filters={
                        "name": ["in", grn_names],
                        "docstatus": 1,
                        "from_finishing": 1,
                        "is_return": 0,
                    },
                    fields=["posting_date"],
                    pluck="posting_date",
                )
                if dates:
                    updates["finishing_end_date"] = max(dates)

        if updates:
            frappe.db.set_value("Finishing Plan", fp.name, updates, update_modified=False)
