frappe.ui.form.on("Essdee Debit", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status === "Debit Requested") {
			frappe.call({
				method: "production_api.production_api.doctype.purchase_invoice.purchase_invoice.get_merch_roles",
				callback(r) {
					if (r.message === "merch_manager") {
						frm.add_custom_button(__("Approve"), () => {
							frappe.confirm(
								__("Are you sure you want to approve this debit?"),
								() => {
									frappe.call({
										method: "production_api.production_api.doctype.essdee_debit.essdee_debit.approve_debit",
										args: { name: frm.doc.name },
										callback() {
											frm.reload_doc();
										},
									});
								},
							);
						}).addClass("btn-primary");
					}
				},
			});
		}
	},
});
