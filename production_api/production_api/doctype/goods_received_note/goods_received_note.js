// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Goods Received Note', {
	refresh: function (frm) {
		// frm.toggle_enable(['supplier'], false);
		// frm.toggle_display(['supplier'], true);
	},
	against_id: function (frm) {
		if (frm.doc["against_id"] && frm.doc.against == "Purchase Order") {
			frappe.call({
				method: "production_api.production_api.doctype.purchase_order.purchase_order.get_po_details",
				args: {"purchase_order": frm.doc.against_id },
				callback: function(r) {
					if (r.message) {
						console.log(r)
						frm.set_value("supplier", r.message["supplier"]);
						frm.set_value("supplier_contact", r.message["contact"]);
						frm.set_value("supplier_address", r.message["address"]);
					}
				}
			})
		}
	},
	supplier: function(frm) {
		if (frm.doc.supplier) {
			frappe.call({
				method: "production_api.production_api.doctype.supplier.supplier.get_primary_address",
				args: {"supplier": frm.doc.supplier},
				callback: function(r) {
					if (r.message) {
						frm.set_value('supplier_address', r.message)
					} else {
						frm.set_value('supplier_address', '')
					}
				}
			})
		}
	},
});
