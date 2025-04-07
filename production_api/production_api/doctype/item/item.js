// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item', {
	setup: function(frm) {
		frm.set_query('additional_parameter_value', 'additional_parameters', (doc, cdt, cdn) => {
			let child = locals[cdt][cdn]
			if (!child.additional_parameter_key){
				frappe.throw("Set Additional Parameter Key")
			}
			return {
				filters: {
					key: child.additional_parameter_key,
				}
			}
		});
		
		frm.get_docfield('additional_parameters', 'additional_parameter_value').get_route_options_for_new_doc = (field) => {
			return {
				key: field.doc.additional_parameter_key,
			}
		};
		frm.set_query('default_unit_of_measure', (doc) => {
			return {
				filters: {
					secondary_only: 0,
				}
			}
		});
		frm.set_query('item_group', function () {
            return {
                filters: {
                    is_group: 0 // only leaf item groups
                }
            };
        });
	},

	refresh: function(frm) {
		if (frm.doc.__islocal) {
			hide_field(["attribute_list_html", "dependent_attribute_details_html", "price_html"]);
		} else {
			unhide_field(["attribute_list_html", "dependent_attribute_details_html", "price_html"]);

			frm.page.add_menu_item(__('Rename'), function() {
				let d = new frappe.ui.Dialog({
					title: __("Rename"),
					fields: [
						{
							label: 'Brand',
							fieldname: "brand",
							fieldtype: "Link",
							options: 'Brand',
							default: frm.doc.brand,
						},
						{
							label: 'New Name',
							fieldname: "name",
							fieldtype: "Data",
							reqd: 1,
							default: frm.doc.name1,
						},
					],
				});
				d.show();
				d.set_primary_action(__("Rename"), (values) => {
					d.disable_primary_action();
					d.hide();
					rename_item_name(frm, values.name, values.brand)
						.then(() => {
							d.hide();
						})
						.catch(() => {
							d.enable_primary_action();
						});
				});
			});

			// Setting the HTML for the attribute list
			$(frm.fields_dict['attribute_list_html'].wrapper).html("");
			new frappe.production.ui.ItemAttributeList({
				wrapper: frm.fields_dict["attribute_list_html"].wrapper,
				attr_values: frm.doc.__onload["attr_list"]
			});

			// Setting the HTML for the attribute list
			$(frm.fields_dict['dependent_attribute_details_html'].wrapper).html("");
			new frappe.production.ui.ItemDependentAttributeDetail(frm.fields_dict["dependent_attribute_details_html"].wrapper);

			// Setting the HTML for Item Price List
			$(frm.fields_dict['price_html'].wrapper).html("");
			new frappe.production.ui.ItemPriceList({
				wrapper: frm.fields_dict["price_html"].wrapper,
			});
		}
	}
});

function rename_item_name(frm, name, brand) {
	let confirm_message = null;
	const docname = frm.doc.name;
	const doctype = frm.doctype;

	if (name) {
		const warning = __("This cannot be undone");
		const message = __("Are you sure you want to merge {0} with {1}?", [
			docname.bold(),
			name.bold(),
		]);
		confirm_message = `${message}<br><b>${warning}<b>`;
	}

	let rename_document = () => {
		return frappe
			.xcall("production_api.production_api.doctype.item.item.rename_item", {
				docname,
				name: name,
				brand: brand,
				// enqueue: true,
				freeze: true,
				freeze_message: __("Updating related fields..."),
			})
			.then((new_docname) => {
				const reload_form = (input_name) => {
					$(document).trigger("rename", [doctype, docname, input_name]);
					if (locals[doctype] && locals[doctype][docname]){
						delete locals[doctype][docname];
					}
					frm.reload_doc();
				};

				// handle document renaming queued action
				if (name && new_docname == docname) {
					frappe.socketio.doc_subscribe(doctype, name);
					frappe.realtime.on("doc_update", (data) => {
						if (data && data.doctype && data.docname && data.doctype == doctype && data.name != docname) {
							reload_form(data.name);
							frappe.show_alert({
								message: __("Document renamed from {0} to {1}", [
									docname.bold(),
									data.name.bold(),
								]),
								indicator: "success",
							});
						}
					});
					frappe.show_alert(
						__("Document renaming from {0} to {1} has been queued", [
							docname.bold(),
							input_name.bold(),
						])
					);
				}

				// handle document sync rename action
				if (name && (new_docname || input_name) != docname) {
					reload_form(new_docname || input_name);
				}
			});
	};

	return new Promise((resolve, reject) => {
		rename_document().then(resolve).catch(reject);
	});
}
