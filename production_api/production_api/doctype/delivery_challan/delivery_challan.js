// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Delivery Challan", {
    setup(frm){
        frm.set_query('from_address', function(doc) {
			if(!doc.from_location) {
				frappe.throw(__("Please set {0}",[__(frappe.meta.get_label(doc.doctype, 'supplier', doc.name))]));
			}
			return {
				query: 'frappe.contacts.doctype.address.address.address_query',
				filters: {
					link_doctype: 'Supplier',
					link_name: doc.from_location
				}
			};
		});
        frm.set_query('supplier_address', function(doc) {
			if(!doc.supplier) {
				frappe.throw(__("Please set {0}",[__(frappe.meta.get_label(doc.doctype, 'supplier', doc.name))]));
			}
			return {
				query: 'frappe.contacts.doctype.address.address.address_query',
				filters: {
					link_doctype: 'Supplier',
					link_name: doc.supplier
				}
			};
		});
		// frm.set_query("from_location", function(doc) {
		// 	let type = "Accepted"
		// 	if(doc.is_rework){
		// 		type = "Rework"
		// 	}
		// 	return {
		// 		filters: {
		// 			"type":type,
		// 		}
		// 	}
		// })
    },
    refresh(frm){
        frm.set_query('work_order',() => {
            return {
                filters : {
                    "docstatus" : 1,
                    "is_delivered" : 0,
                    "open_status":"Open",
                }
            }
        })
        $(frm.fields_dict['deliverable_items'].wrapper).html("")
        if(frm.doc.__onload && frm.doc.__onload.deliverable_item_details) {
            frm.doc['deliverable_item_details'] = JSON.stringify(frm.doc.__onload.deliverable_item_details);
            frm.deliverable_items = new frappe.production.ui.Delivery_Challan(frm.fields_dict['deliverable_items'].wrapper,frm.doc.__onload.deliverable_item_details )
            frm.deliverable_items.update_status();
        }
    },
	work_order:function(frm) {
        frm.doc.items = [];
        $(frm.fields_dict['deliverable_items'].wrapper).html("")
        if (! frm.doc.work_order){
            return;
        }
        else{
            frappe.call({
                method:"production_api.production_api.doctype.delivery_challan.delivery_challan.get_deliverables",
                args:{
                    "work_order": frm.doc.work_order,
                },
                callback: function(response){
                    if(response.message){
                        frm.deliverable_items = new frappe.production.ui.Delivery_Challan(frm.fields_dict['deliverable_items'].wrapper, response.message.items)
                        frm.set_value('supplier',response.message.supplier)
                        frm.set_value('supplier_address',response.message.supplier_address)        
                    }
                }
            })
        }
	},
    validate: function(frm){
        let deliverables = frm.deliverable_items.get_data()
        frm.doc['deliverable_item_details'] = JSON.stringify(deliverables)
    },
	from_location: function(frm) {
		if (frm.doc.from_location) {
			frappe.production.ui.eventBus.$emit("supplier_updated", frm.doc.from_location)
		}
		if (frm.doc.from_location) {
			frappe.call({
				method: "production_api.production_api.doctype.supplier.supplier.get_primary_address",
				args: {
					"supplier": frm.doc.from_location
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('from_address', r.message)
					}
				}
			})
		}
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
					}
				}
			})
		}
	},
    from_address: function(frm) {
		if (frm.doc['from_address']) {
			frappe.call({
				method: "production_api.production_api.doctype.purchase_order.purchase_order.get_address_display",
				args: {
					"address_dict": frm.doc['from_address'] 
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('from_address_details', r.message)
					}
				}
			})
		} 
		else {
			frm.set_value('from_address_details', '');
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
});
