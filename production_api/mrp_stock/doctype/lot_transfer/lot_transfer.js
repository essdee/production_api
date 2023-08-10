// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Lot Transfer', {
	refresh: function(frm) {
		$(frm.fields_dict['item_html'].wrapper).html("");
		frm.itemEditor = new frappe.production.ui.LotTransferItem(frm.fields_dict["item_html"].wrapper);

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

	validate: function(frm) {
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
	},

	purpose: function(frm) {
		if (frm.doc.purpose) {
			frappe.production.ui.eventBus.$emit("purpose_updated", frm.doc.purpose)
		}
		frm.cscript.toggle_related_fields(frm.doc);
		frm.cscript.set_mandatory_fields(frm.doc);
	}
});
