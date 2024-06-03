// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Process", {
	refresh(frm) {
        frm.set_query("process_name", "process_details", function (frm) {
            return {
                filters:
                {
                    "is_group": 0,
                }
            };
        });
	},
});