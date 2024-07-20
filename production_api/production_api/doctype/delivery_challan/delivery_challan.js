// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Delivery Challan", {
    setup:function(frm){
		frm.set_query('from_address', function(doc) {
			if(!doc.from_location) {
				frappe.throw(__("Please set From Location",
					[__(frappe.meta.get_label(doc.doctype, 'supplier', doc.name))]));
			}

			return {
				query: 'frappe.contacts.doctype.address.address.address_query',
				filters: {
					link_doctype: 'Supplier',
					link_name: doc.from_location
				}
			};
		});
	},
    refresh(frm){
        frm.set_query('work_order',() => {
            return {
                filters : {
                    "docstatus" : 1,
					"open_status": 'Open',
                }
            }
        })
        $(frm.fields_dict['deliverable_items'].wrapper).html("")
        if(frm.doc.__onload && frm.doc.__onload.deliverable_item_details) {
            frm.doc['deliverable_item_details'] = JSON.stringify(frm.doc.__onload.deliverable_item_details);
            frm.deliverable_items = new frappe.production.ui.Delivery_Challan(frm.fields_dict['deliverable_items'].wrapper,frm.doc.__onload.deliverable_item_details )
        }
        frm.deliverable_items.update_status();
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
                        frm.set_value('supplier', response.message.supplier)
                        frm.set_value('supplier_address',response.message.supplier_address)
                        frm.deliverable_items = new frappe.production.ui.Delivery_Challan(frm.fields_dict['deliverable_items'].wrapper, response.message.item)
                    }
                }
            })
        }
	},
    validate: function(frm){
        let deliverables = frm.deliverable_items.get_data()
        frm.doc['deliverable_item_details'] = JSON.stringify(deliverables)
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
	from_location: function(frm){
		if(frm.doc.from_location){
			frappe.call({
				method: "production_api.mrp_stock.doctype.warehouse.warehouse.get_warehouse",
				args: {
					"supplier":frm.doc.from_location,
				},
				callback: function(response){
					if(response.message){
						frm.set_value('from_warehouse',response.message)
					}
					else{
						frm.set_value('from_warehouse','')
					}
				}
			})
		}
		else{
			frm.set_value('from_warehouse','')
		}
	},
	supplier: function(frm){
		if(frm.doc.supplier){
			frappe.call({
				method: "production_api.mrp_stock.doctype.warehouse.warehouse.get_warehouse",
				args: {
					"supplier":frm.doc.supplier,
				},
				callback: function(response){
					if(response.message){
						frm.set_value('supplier_warehouse',response.message)
					}
					else{
						frm.set_value('supplier_warehouse','')
					}
				}
			})
		}
		else{
			frm.set_value('supplier_warehouse','')
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
