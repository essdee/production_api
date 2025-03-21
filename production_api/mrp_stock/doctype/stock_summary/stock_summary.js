// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Stock Summary", {
	refresh(frm) {
        frm.disable_save();
        $(frm.fields_dict['stock_summary_html'].wrapper).html("");     
		new frappe.production.ui.StockSummary(frm.fields_dict['stock_summary_html'].wrapper);
	},
});
