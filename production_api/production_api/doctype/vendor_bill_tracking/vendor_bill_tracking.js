// Copyright (c) 2025, Aerele Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Vendor Bill Tracking", {
  async refresh(frm) {
		$(frm.fields_dict["delivery_person_suggestion_html"].wrapper).html("");
		if (frm.doc.docstatus == 0) {
			frm.delivery_person_suggestion = new frappe.production.ui.SuggestedVendorBillDeliveryPerson(
				frm.fields_dict["delivery_person_suggestion_html"].wrapper
			);
			if (!frm.is_new()) {
				frm.trigger("supplier");
			}
		}

		if (!frm.is_new() && frm.doc.docstatus == 1) {
			if (!['Closed', 'Cancelled'].includes(frm.doc.form_status)) {
				frm.add_custom_button(__("Assign"), () => {
					show_and_get_assignment(frm);
				});
			}
			frm.page.btn_secondary.hide();
			if (!frm.doc.purchase_invoice && !frm.doc.mrp_purchase_invoice) {
				if ( frappe.user.has_role("Accounts Manager") || frappe.user.has_role("Accounts User")) {
					frm.add_custom_button(__("Cancel"), () => {
						get_remarks_and_cancel(frm);
					});
					frm.add_custom_button(__("Create MRP PI"), () => {
						let x = frappe.model.get_new_doc("Purchase Invoice");
						x.supplier = frm.doc.supplier;
						x.bill_date = frm.doc.bill_date;
						x.bill_no = frm.doc.bill_no;
						x.vendor_bill_tracking = frm.doc.name;
						frappe.set_route("Form", x.doctype, x.name);
					});
					frm.add_custom_button(__("Create ERP PI"), () => {
						frappe.call({
							method:"production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.get_accounting_system_purchase_invoice",
							args: {
								doc_name: frm.doc.name,
							},
							callback: (r) => {
								const defaults = {
									supplier: r.message.supplier,
									bill_no: r.message.bill_no,
									bill_date: r.message.bill_date,
									doctype: r.message.doctype,
									vendor_bill_tracking: r.message.vendor_bill_tracking,
									action: "new",
								};
								const params = new URLSearchParams(defaults).toString();
								window.open(`${r.message.url}/app/erp-mrp-connector?${params}`);
							},
						});
					});
				}
			}
			if(frm.doc.purchase_invoice){
				frm.add_custom_button("Show Purchase Invoice", ()=> {
					frappe.call({
						method: "production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.get_erp_inv_link",
						args: {
							"name": frm.doc.name,
						},
						callback: function(r) {
							if (r.message) {
								window.open(r.message, "_blank");
							}
						}
					})
				})
			}
			if(frm.doc.mrp_purchase_invoice){
				frm.add_custom_button("Show MRP Purchase Invoice", ()=> {
					frappe.open_in_new_tab = true
					frappe.set_route("Form", "Purchase Invoice", frm.doc.mrp_purchase_invoice)
				})
			}
			let show_receive = await show_bill_received(frm);
			if (show_receive && frm.doc.form_status != "Closed") {
				frm.add_custom_button(__("Bill Recieved"), () => {
					frappe.call({
						method:"production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.make_bill_recieved_acknowledgement",
						args: {
							doc_name: frm.doc.name,
						},
						callback: (r) => {
							frm.reload_doc();
						},
					});
				});
			}
		}
	},
	supplier(frm) {
		if (frm.doc.supplier) {
			frm.delivery_person_suggestion.update_for_new_supplier(frm.doc.supplier);
			if (!frm.doc.supplier) {
				frm.set_value("delivery_mob_no", null);
			}
		}
	},
});
async function show_bill_received(frm) {
	if (!frm.doc.assigned_to) return false;
	let last_item = null;
	for (const item of frm.doc.vendor_bill_tracking_history) {
		if (item.assigned_to === frm.doc.assigned_to) last_item = item;
	}
	if (!last_item || last_item.received) return false;
	const resp = await new Promise((resolve, reject) => {
		frappe.call({
			method:"production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.check_for_can_show_receive_btn",
			args: { name: frm.doc.name },
			callback: (r) => resolve(r.message),
			error: (e) => reject(e),
		});
	});
	return resp;
}

function get_remarks_and_cancel(frm) {
	let dialog = new frappe.ui.Dialog({
		title: "Cancelling...",
		fields: [
			{
				label: "Cancel Reason",
				fieldname: "cancel_reason",
				fieldtype: "Small Text",
				reqd: 1,
			},
		],
		primary_action_label: "Cancel",
		primary_action: (values) => {
			make_cancel_action(values["cancel_reason"]);
			dialog.hide();
		},
	});
	dialog.show();
}

function make_cancel_action(reason) {
	frappe.call({
		method:"production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.cancel_vendor_bill",
		freeze: true,
		freeze_msg: "Cancelling Document",
		args: {
			name: cur_frm.doc.name,
			cancel_reason: reason,
		},
		callback: (response) => {
			cur_frm.reload_doc();
		},
	});
}

function show_and_get_assignment(frm) {
 	let dialog = new frappe.ui.Dialog({
		title: "Assign Vendor Bill",
		fields: [
			{
				label: "Assigned To",
				fieldname: "assigned_to",
				fieldtype: "Link",
				options: "Department",
				reqd: 1,
			},
			{
				label: "Remarks",
				fieldname: "remarks",
				fieldtype: "Small Text",
			},
		],
		primary_action_label: "Submit",
		primary_action: (values) => {
			make_assignement_action(values);
			dialog.hide();
		},
	});
	dialog.show();
}
function make_assignement_action(values) {
	frappe.call({
		method:"production_api.production_api.doctype.vendor_bill_tracking.vendor_bill_tracking.assign_vendor_bill",
		freeze: true,
		freeze_msg: "Assigning Document",
		args: {
			name: cur_frm.doc.name,
			assigned_to: values["assigned_to"],
			remarks: values["remarks"],
		},
		callback: (response) => {
			cur_frm.reload_doc();
		},
	});
}
