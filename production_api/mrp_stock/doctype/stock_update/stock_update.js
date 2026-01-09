// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Stock Update", {
	refresh(frm) {
        $(".layout-side-section").css("display", "None")
		$(frm.fields_dict['stock_update_html'].wrapper).html("");
		frm.itemEditor = new frappe.production.ui.StockUpdateItem(frm.fields_dict["stock_update_html"].wrapper);

		if(frm.doc.__onload && frm.doc.__onload.item_details) {
			frm.doc['item_details'] = JSON.stringify(frm.doc.__onload.item_details);
			frm.itemEditor.load_data(frm.doc.__onload.item_details);
		} else {
			frm.itemEditor.load_data([]);
		}
		frm.itemEditor.update_status();
		frappe.production.ui.eventBus.$on("stock_updated", e => {
			frm.dirty();
		})
	},
    validate(frm) {
		if(frm.itemEditor){
			let items = frm.itemEditor.get_items();
			if(items && items.length > 0) {
				frm.doc['item_details'] = JSON.stringify(items);
			} else {
				frappe.throw(__('Add Items to continue'));
			}
		}
		else {
			frappe.throw(__('Please refresh and try again.'));
		}
	}
});
