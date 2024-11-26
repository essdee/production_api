// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Action Master Detail", {
    action: function (frm, cdt, cdn) {
        let row = frappe.get_doc(cdt, cdn);
        frappe.call({
            method: "production_api.essdee_production.doctype.action_master.action_master.get_work_station",
            args: {
                action: row.action,
            },
            callback: function (r) {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, "work_station", r.message);
                    frm.refresh_field("details");
                }
            },
        });
    },
});
