// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Supplier', {
	refresh: function (frm) {
		frappe.dynamic_link = { doc: frm.doc, fieldname: 'name', doctype: 'Supplier' };
		if (frm.doc.__islocal) {
			hide_field(["address_html", "contact_html", "item_price_list_html"]);
			frappe.contacts.clear_address_and_contact(frm);
		} else {
			unhide_field(["address_html", "contact_html", "item_price_list_html"]);
			frappe.contacts.render_address_and_contact(frm);

			// Setting the HTML for Item Price List
			$(frm.fields_dict['item_price_list_html'].wrapper).html("");
			// new frappe.production.ui.ItemPriceList({
			// 	wrapper: frm.fields_dict["item_price_list_html"].wrapper,
			// });
			frappe.production.ui.ItemDetail(frm.fields_dict['item_price_list_html'].wrapper, 'Supplier', frm.doc.name);
		}
	}
});
