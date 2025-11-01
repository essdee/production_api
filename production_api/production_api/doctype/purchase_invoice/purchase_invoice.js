// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Purchase Invoice', {
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
			if (!doc.against) {
				frappe.throw("Please Set Against")
			}
			return {
				filters: [
					["purchase_invoice_name", "is", "not set"],
					["docstatus", "=", "1"],
					["supplier", "=", doc.supplier],
					["against", '=', doc.against]
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

		if (frm.doc.docstatus == 1 && frm.doc.erp_inv_docstatus == 0) {
			frm.add_custom_button(__('Submit Bill'), function() {
				frappe.call({
					method: "production_api.production_api.doctype.purchase_invoice.purchase_invoice.submit_erp_invoice",
					args: {
						"name": frm.doc.name,
					},
					freeze: true,
					freeze_message: __("Submitting Bill..."),
					callback: function(r) {
						if (r.message) {
							console.log(r.message)
						}
					}
				})
			})
		}
		$(frm.fields_dict['work_order_details_html'].wrapper).html("")
		if(frm.doc.__onload && frm.doc.__onload.item_details){
			frm.pi_wo_items = new frappe.production.ui.InvoiceWoItems(frm.fields_dict['work_order_details_html'].wrapper)
			frm.doc['item_details'] = frm.doc.__onload.item_details
			frm.pi_wo_items.load_data(frm.doc.__onload.item_details)
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
				"grns": grns,
				"against": frm.doc.against,
				"supplier": frm.doc.supplier
			},
			callback: function(r){
				if (r.message){
					frm.set_value('items', r.message.items)
					frm.set_value("grn_grand_total", r.message.total)
					frm.set_value("total_quantity", r.message.total_quantity)
					frm.set_value("pi_work_order_billed_details", r.message.wo_items)
					frm.set_value("allow_to_change_rate", r.message.allow_to_change_rate)
				}
			}
		})
	}
});
