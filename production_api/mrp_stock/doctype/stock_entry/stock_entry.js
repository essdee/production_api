// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.provide("production_api.mrp_stock");

frappe.ui.form.on('Stock Entry', {
	refresh: function(frm) {
		if (frm.doc.docstatus === 1) {
			if (frm.doc.purpose=='Send to Warehouse' && frm.doc.per_transferred < 100) {
				frm.add_custom_button(__('End Transit'), function() {
					frappe.model.open_mapped_doc({
						method: "production_api.mrp_stock.doctype.stock_entry.stock_entry.make_stock_in_entry",
						frm: frm
					})
				});
			}

			if (frm.doc.per_transferred > 0) {
				frm.add_custom_button(__('Received Stock Entries'), function() {
					frappe.route_options = {
						'outgoing_stock_entry': frm.doc.name,
						'docstatus': ['!=', 2]
					};

					frappe.set_route('List', 'Stock Entry');
				}, __("View"));
			}
		}
	},

	purpose: function(frm) {
		if (frm.doc.purpose) {
			frappe.production.ui.eventBus.$emit("purpose_updated", frm.doc.purpose)
		}
		frm.cscript.toggle_related_fields(frm.doc);
		frm.cscript.set_mandatory_fields(frm.doc);
	}
});

frappe.ui.form.on('Stock Entry Detail', {

});

production_api.mrp_stock.StockEntry = class StockEntry extends frappe.ui.form.Controller {
	refresh() {
		this.toggle_related_fields(this.frm.doc);
		this.set_mandatory_fields(this.frm.doc);
		$(this.frm.fields_dict['item_html'].wrapper).html("");
		this.frm.itemEditor = new frappe.production.ui.StockEntryItem(this.frm.fields_dict["item_html"].wrapper);

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

	toggle_related_fields(doc) {
		this.frm.toggle_enable("from_warehouse", doc.purpose!='Material Receipt');
		this.frm.toggle_enable("to_warehouse", doc.purpose!='Material Issue');
	}
	
	set_mandatory_fields(doc) {
		this.frm.toggle_reqd("from_warehouse", doc.purpose!='Material Receipt');
		this.frm.toggle_reqd("to_warehouse", doc.purpose!='Material Issue');
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

extend_cscript(cur_frm.cscript, new production_api.mrp_stock.StockEntry({frm: cur_frm}));
