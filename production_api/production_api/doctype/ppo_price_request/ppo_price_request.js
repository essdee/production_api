// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("PPO Price Request", {
	refresh(frm) {
		if (frm.doc.status === "Pending" && frappe.user_roles.includes("System Manager")) {
			frm.add_custom_button(__("Approve"), () => {
				frappe.call({
					method: "production_api.production_api.doctype.ppo_price_request.ppo_price_request.approve_ppo_price_request",
					args: { name: frm.doc.name },
					callback: function () {
						frm.reload_doc();
						frappe.show_alert({ message: __("Price change approved"), indicator: "green" });
					}
				});
			}, __("Action"));

			frm.add_custom_button(__("Reject"), () => {
				frappe.call({
					method: "production_api.production_api.doctype.ppo_price_request.ppo_price_request.reject_ppo_price_request",
					args: { name: frm.doc.name },
					callback: function () {
						frm.reload_doc();
						frappe.show_alert({ message: __("Price change rejected"), indicator: "red" });
					}
				});
			}, __("Action"));
		}
	}
});
