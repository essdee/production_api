// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Supplier', {
	refresh: function (frm) {
		frappe.dynamic_link = { doc: frm.doc, fieldname: 'name', doctype: 'Supplier' };
		if (frm.doc.__islocal) {
			hide_field(["address_html", "contact_html"]);
			frappe.contacts.clear_address_and_contact(frm);
		} else {
			unhide_field(["address_html", "contact_html", "price_html"]);
			frappe.contacts.render_address_and_contact(frm);
			
			// Setting the HTML for Item Price List
			$(frm.fields_dict['price_html'].wrapper).html("");
			new frappe.production.ui.ItemPriceList({
				wrapper: frm.fields_dict["price_html"].wrapper,
			});
		}
		frm.trigger("setup_terms_and_condition_update");
	},
	setup_terms_and_condition_update(frm) {
		if (frm.is_new() || frm.has_perm("write") || !frm.has_perm("read")) {
			return;
		}
		const field = frm.fields_dict.terms_and_condition;
		if (!field) {
			return;
		}
		field.df.read_only = 0;
		field.df.get_status = () => "Write";
		field.refresh();
	},
	terms_and_condition(frm) {
		if (
			frm.__updating_terms_and_condition ||
			frm.is_new() ||
			frm.has_perm("write") ||
			!frm.has_perm("read")
		) {
			return;
		}

		frappe.call({
			method: "production_api.production_api.doctype.supplier.supplier.update_terms_and_condition",
			args: {
				supplier: frm.doc.name,
				terms_and_condition: frm.doc.terms_and_condition || "",
			},
			freeze: true,
			freeze_message: __("Updating Terms and Condition..."),
			callback(r) {
				frm.__updating_terms_and_condition = true;
				frm.doc.terms_and_condition = r.message?.terms_and_condition || "";
				frm.refresh_field("terms_and_condition");
				frm.doc.__unsaved = 0;
				frm.toolbar.set_primary_action();
				frm.__updating_terms_and_condition = false;
				frappe.show_alert({
					message: __("Terms and Condition updated"),
					indicator: "green",
				});
				frm.reload_doc();
			},
			error() {
				frm.reload_doc();
			},
		});
	},
});
