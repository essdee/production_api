// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Time and Action Weekly Review Report", {
    refresh(frm) {
        $(".layout-side-section").css("display", "None");
        $(frm.fields_dict['report_data_html'].wrapper).html("");     
		new frappe.production.ui.TimeAndActionWeeklyReport(frm.fields_dict['report_data_html'].wrapper);
    },
});

