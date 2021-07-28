// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Supplier', {
	refresh: function (frm) {
		frappe.dynamic_link = { doc: frm.doc, fieldname: 'name', doctype: 'Supplier' };
		if (frm.doc.__islocal) {
			hide_field(["address_html", "contact_html"]);
			frappe.contacts.clear_address_and_contact(frm);
		} else {
			unhide_field(["address_html", "contact_html"]);
			frappe.contacts.render_address_and_contact(frm);
		}
	}
});
