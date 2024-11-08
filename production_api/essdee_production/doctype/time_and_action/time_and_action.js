// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Time and Action", {
	refresh(frm) {
        frm.set_df_property("details","cannot_add_rows",true)
        frm.set_df_property("details","cannot_delete_rows",true)
	},
});
