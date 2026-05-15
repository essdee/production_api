// Copyright (c) 2026, Essdee and contributors
// For license information, please see license.txt

frappe.provide("production_api.mrp_stock");

frappe.ui.form.on("Item Conversion", {
	setup: function(frm) {
		frm.set_query("from_item", function() {
			return { filters: { is_stock_item: 1 } };
		});
		frm.set_query("to_item", function() {
			return { filters: { is_stock_item: 1 } };
		});
	},

	refresh: function(frm) {
		frm.page.btn_secondary.hide();

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button("Cancel", () => {
				frm._cancel();
			});
		}
	},

	warehouse: function(frm) {
		if (frm.itemConversion) {
			frm.itemConversion.refresh_from_rates();
		}
	},

	from_item: function(frm) {
		if (frm.itemConversion) {
			frm.itemConversion.refresh_from_rates();
		}
	},
});

production_api.mrp_stock.ItemConversion = class ItemConversion extends frappe.ui.form.Controller {
	refresh() {
		$(".layout-side-section").css("display", "None");
		$(this.frm.fields_dict["item_conversion_html"].wrapper).html("");
		this.frm.itemConversion = new frappe.production.ui.ItemConversion(
			this.frm.fields_dict["item_conversion_html"].wrapper
		);

		this.frm.itemConversion.load_data({
			from_items: this.frm.doc.__onload ? this.frm.doc.__onload.from_item_details || [] : [],
			to_items: this.frm.doc.__onload ? this.frm.doc.__onload.to_item_details || [] : [],
		});
		this.frm.itemConversion.update_status();

		frappe.production.ui.eventBus.$on("item_conversion_updated", () => {
			this.frm.dirty();
		});
	}

	validate() {
		if (!this.frm.itemConversion) {
			frappe.throw(__("Please refresh and try again."));
		}

		const items = this.frm.itemConversion.get_items();
		if (!items.from_items || !items.from_items.length) {
			frappe.throw(__("Add From Items to continue"));
		}
		if (!items.to_items || !items.to_items.length) {
			frappe.throw(__("Add To Items to continue"));
		}

		this.frm.doc.from_item_details = JSON.stringify(items.from_items);
		this.frm.doc.to_item_details = JSON.stringify(items.to_items);
		this.frm.doc.from_total_amount = items.from_total_amount;
		this.frm.doc.to_total_amount = items.to_total_amount;
		this.frm.doc.difference_amount = items.difference_amount;
	}

	before_submit() {
		const items = this.frm.itemConversion.get_items();
		if (items.has_difference) {
			frappe.throw(__("From Item value and To Item value must match before submit."));
		}
	}
};

extend_cscript(cur_frm.cscript, new production_api.mrp_stock.ItemConversion({ frm: cur_frm }));
