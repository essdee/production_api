// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.provide("production_api.stock");

frappe.ui.form.on('Stock Reconciliation', {
	
});

frappe.ui.form.on('Stock Reconciliation Item', {

});

production_api.stock.StockReconciliation = class StockReconciliation extends frappe.ui.form.Controller {
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

extend_cscript(cur_frm.cscript, new production_api.stock.StockReconciliation({frm: cur_frm}));
