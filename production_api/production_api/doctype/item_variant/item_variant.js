// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item Variant', {
	refresh: function(frm) {
		if (!frm.doc.__islocal) {
			frm.page.add_menu_item(__('Rename'), function() {
				rename_item_name(frm).then(() => console.log("Rename done")).catch((err) => console.log(err));
			});
		}
	}
});

function rename_item_name(frm) {
	const docname = frm.doc.name;
	const doctype = frm.doctype;

	// if (name) {
	// 	const warning = __("This cannot be undone");
	// 	const message = __("Are you sure you want to merge {0} with {1}?", [
	// 		docname.bold(),
	// 		name.bold(),
	// 	]);
	// 	confirm_message = `${message}<br><b>${warning}<b>`;
	// }

	let rename_document = () => {
		return frappe
			.xcall("production_api.production_api.doctype.item_variant.item_variant.rename_item_variant", {
				docname,
				variant: docname,
				// name: name,
				// brand: brand,
				// enqueue: true,
				freeze: true,
				freeze_message: __("Renaming..."),
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
				if (docname != new_docname) {
					reload_form(new_docname);
				} else {
					frm.reload_doc()
				}
			});
	};

	return new Promise((resolve, reject) => {
		rename_document().then(resolve).catch(reject);
	});
}
