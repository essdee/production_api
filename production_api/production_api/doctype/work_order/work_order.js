// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Work Order", {
	refresh(frm) {
        $(frm.fields_dict['deliverable_items'].wrapper).html("")
        frm.deliverable_items = new frappe.production.ui.Deliverables(frm.fields_dict["deliverable_items"].wrapper);
        
		$(frm.fields_dict['receivable_items'].wrapper).html("")
        frm.receivable_items = new frappe.production.ui.Receivables(frm.fields_dict["receivable_items"].wrapper)
		
		if(frm.doc.__onload && frm.doc.__onload.deliverable_item_details) {
            frm.doc['deliverable_item_details'] = JSON.stringify(frm.doc.__onload.deliverable_item_details);
		    frm.deliverable_items.load_data(frm.doc.__onload.deliverable_item_details);
        }
        else{
            frm.deliverable_items.load_data([])
        }
        frm.deliverable_items.update_status();
        
		if(frm.doc.__onload && frm.doc.__onload.receivable_item_details) {
            frm.doc['receivable_item_details'] = JSON.stringify(frm.doc.__onload.receivable_item_details);
		    frm.receivable_items.load_data(frm.doc.__onload.receivable_item_details);
        }
        else{
            frm.deliverable_items.load_data([])
        }
        frm.receivable_items.update_status()
        
		frappe.production.ui.eventBus.$on("wo_updated", e => {
			frm.dirty();
		})
	},
    validate(frm) {
        let deliverables = frm.deliverable_items.get_deliverables_data();
		frm.doc['deliverable_item_details'] = JSON.stringify(deliverables);
        
		let receivables = frm.receivable_items.get_receivables_data();
		frm.doc['receivable_item_details'] = JSON.stringify(receivables);
    },

    supplier: function(frm) {
		if (frm.doc.supplier) {
			frappe.production.ui.eventBus.$emit("supplier_updated", frm.doc.supplier)
		}
		if (frm.doc.supplier) {
			frappe.call({
				method: "production_api.production_api.doctype.supplier.supplier.get_primary_address",
				args: {
					"supplier": frm.doc.supplier
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('supplier_address', r.message)
					} else {
						frm.set_value('supplier_address', '')
					}
				}
			})
		}
	},

    supplier_address: function(frm) {
		if (frm.doc['supplier_address']) {
			frappe.call({
				method: "production_api.production_api.doctype.purchase_order.purchase_order.get_address_display",
				args: {
					"address_dict": frm.doc['supplier_address'] 
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('supplier_address_details', r.message)
					}
				}
			})
		} 
		else {
			frm.set_value('supplier_address_details', '');
		}
	},

    delivery_address: function(frm) {
		if (frm.doc['delivery_address']) {
			frappe.call({
				method: "production_api.production_api.doctype.purchase_order.purchase_order.get_address_display",
				args: {
					"address_dict": frm.doc['delivery_address'] 
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('delivery_address_details', r.message)
					}
				}
			})
		} 
		else {
			frm.set_value('delivery_address_details', '');
		}
	},
});
