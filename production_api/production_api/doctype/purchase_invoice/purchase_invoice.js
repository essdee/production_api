// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Purchase Invoice', {
	// refresh: function(frm) {

	// }

	setup: function(frm) {
		frm.set_query('supplier', (doc) => {
			return {
				filters: {
					disabled: 0,
				}
			}
		});
		frm.set_query('grn', 'grn', (doc) => {
			if (!doc.supplier) {
				frappe.throw("Please Set Supplier");
			}
			return {
				filters: [
					["purchase_invoice_name", "is", "not set"],
					["docstatus", "=", "1"],
					["supplier", "=", doc.supplier]
				]
			}
		});
	},

	refresh: function(frm) {
		if (frm.doc.docstatus == 1 && frm.doc.erp_inv_name) {
			frm.add_custom_button(__('Show Bill'), function() {
				frappe.call({
					method: "production_api.production_api.doctype.purchase_invoice.purchase_invoice.get_erp_inv_link",
					args: {
						"name": frm.doc.name,
					},
					callback: function(r) {
						if (r.message) {
							window.open(r.message, "_blank");
						}
					}
				})
			});
		}
	},

	supplier: function(frm) {
		frm.set_value('grn', [])
		frm.set_value('billing_supplier', frm.doc.supplier)
	},

	fetch_grn: function(frm) {
		if (!frm.doc.grn.length) {
			frappe.throw("Please set atleast one GRN")
		}
		let grns = [];
		for (let i = 0;i<frm.doc.grn.length;i++) {
			grns.push(frm.doc.grn[i].grn)
		}
		grns = Array.from(new Set(grns))
		frappe.call({
			method: "production_api.production_api.doctype.purchase_invoice.purchase_invoice.fetch_grn_details",
			args: {
				grns
			},
			callback: function(r){
				if (r.message){
					frm.set_value('items', r.message)

				}
			}
		})
	}
});
