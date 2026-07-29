// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Telegram Approval Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Verify Bot"), () => {
			frappe.call({
				method: "production_api.telegram_approval.api.verify_bot",
				freeze: true,
				callback: (response) => {
					if (response.message) {
						frappe.msgprint(
							__("Connected to Telegram bot @{0}", [response.message.username])
						);
					}
				},
			});
		});

		frm.add_custom_button(__("Configure Webhook"), () => {
			frappe.call({
				method: "production_api.telegram_approval.api.configure_webhook",
				freeze: true,
				callback: () => frm.reload_doc(),
			});
		});

		frm.add_custom_button(__("Webhook Status"), () => {
			frappe.call({
				method: "production_api.telegram_approval.api.get_webhook_status",
				freeze: true,
				callback: (response) => {
					if (response.message) {
						frappe.msgprint(
							`<pre>${frappe.utils.escape_html(
								JSON.stringify(response.message, null, 2)
							)}</pre>`
						);
					}
				},
			});
		});
	},
});
