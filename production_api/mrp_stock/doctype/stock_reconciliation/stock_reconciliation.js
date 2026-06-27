// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.provide("production_api.mrp_stock");

function open_stock_reconciliation_duplicate_dialog(frm, flat_rows) {
	const d = new frappe.ui.Dialog({
		title: __('Duplicate Stock Reconciliation'),
		size: 'extra-large',
		static: true,
		primary_action_label: __('Yes, Duplicate'),
		primary_action: function() {
			if (!d.editor) return;
			const items_data = d.editor.get_items();
			if (!items_data || items_data.length === 0) {
				frappe.show_alert({ message: __('At least one item is required to duplicate.'), indicator: 'red' });
				return;
			}
			frappe.call({
				method: "production_api.mrp_stock.doctype.stock_reconciliation.stock_reconciliation.duplicate_stock_reconciliation",
				args: { stock_reconciliation: frm.doc.name, items_data: items_data },
				freeze: true,
				freeze_message: __('Creating duplicate Stock Reconciliation'),
				callback: function(r) {
					if (r.message) {
						d.hide();
						frappe.set_route('Form', 'Stock Reconciliation', r.message);
					}
				}
			});
		},
		secondary_action_label: __('Close'),
		secondary_action: function() { d.hide(); },
	});
	d.$wrapper.find('.modal-dialog').css('max-width', '1400px');
	const wrapper = $('<div class="duplicate-sr-editor"></div>').appendTo(d.body);
	d.editor = new frappe.production.ui.DuplicateStockReconciliationItemTable(wrapper);
	d.editor.load_data(flat_rows);
	d.show();
	d.$wrapper.on('hidden.bs.modal', function() {
		if (d.editor && d.editor.destroy) d.editor.destroy();
	});
}

frappe.ui.form.on('Stock Reconciliation', {
	refresh: function(frm) {
		frm.set_query("default_warehouse", () => ({ filters: { disabled: 0 } }));
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__('Duplicate'), function() {
				frappe.call({
					method: "production_api.mrp_stock.doctype.stock_reconciliation.stock_reconciliation.get_stock_reconciliation_duplicate_items",
					args: { stock_reconciliation: frm.doc.name },
					freeze: true,
					callback: function(res) {
						open_stock_reconciliation_duplicate_dialog(frm, res.message || []);
					}
				});
			});
		}
	},
});

frappe.ui.form.on('Stock Reconciliation Item', {

});

production_api.mrp_stock.StockReconciliation = class StockReconciliation extends frappe.ui.form.Controller {
	refresh() {
		$(this.frm.fields_dict['item_html'].wrapper).html("");
		this.frm.itemEditor = new frappe.production.ui.StockReconciliationItem(this.frm.fields_dict["item_html"].wrapper);
		if(this.frm.doc.__onload && this.frm.doc.__onload.item_details) {
			this.frm.doc['item_details'] = JSON.stringify(this.frm.doc.__onload.item_details);
			this.frm.itemEditor.load_data(this.frm.doc.__onload.item_details);
		} else {
			this.frm.itemEditor.load_data([]);
		}
		this.frm.itemEditor.update_status();
		frappe.production.ui.eventBus.$on("stock_updated", e => {
			this.frm.dirty();
		})
	}

	validate() {
		if(this.frm.itemEditor){
			let items = this.frm.itemEditor.get_items();
			if(items && items.length > 0) {
				this.frm.doc['item_details'] = JSON.stringify(items);
			} else {
				frappe.throw(__('Add Items to continue'));
			}
		}
		else {
			frappe.throw(__('Please refresh and try again.'));
		}
	}

	items_add(doc, cdt, cdn) {
		var row = frappe.get_doc(cdt, cdn);

		if(!row.s_warehouse) row.s_warehouse = this.frm.doc.from_warehouse;
		if(!row.t_warehouse) row.t_warehouse = this.frm.doc.to_warehouse;
	}

	from_warehouse(doc) {
		this.autofill_warehouse(doc.items, "s_warehouse", doc.from_warehouse);
	}

	to_warehouse(doc) {
		this.autofill_warehouse(doc.items, "t_warehouse", doc.to_warehouse);
	}

	autofill_warehouse(child_table, warehouse_field, warehouse) {
		if (warehouse && child_table && child_table.length) {
			let doctype = child_table[0].doctype;
			$.each(child_table || [], function(i, item) {
				frappe.model.set_value(doctype, item.name, warehouse_field, warehouse);
			});
		}
	}
}

extend_cscript(cur_frm.cscript, new production_api.mrp_stock.StockReconciliation({frm: cur_frm}));
