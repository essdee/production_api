// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Purchase Order', {
	refresh: function(frm) {
		$(frm.fields_dict['item_html'].wrapper).html("");
		frm.newitemvm = frappe.production.ui.PurchaseOrderItem(frm.fields_dict["item_html"].wrapper);
	},

	validate: function(frm) {
		console.log(frm);
		if(frm.newitemvm){
			let items = frm.newitemvm.$children[0].items;
			if(items && items.length > 0){
				frm.doc['item_details'] = JSON.stringify(items);
			}
			else
				frappe.throw(__('Add Items to continue'));
		}
		else{
			frappe.throw(__('Please refresh and try again.'));
		}
	},

	before_save: function(frm) {
		if(frm.newitemvm) {
			console.log(frm.newitemvm);
		}
	}
});
