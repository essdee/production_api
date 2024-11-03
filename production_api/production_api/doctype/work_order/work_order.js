// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt
var val = null
frappe.ui.form.on("Work Order", {
	async refresh(frm) {
		if(!frm.is_new()){
			$(frm.fields_dict['deliverable_items'].wrapper).html("")
			frm.deliverable_items = new frappe.production.ui.Deliverables(frm.fields_dict["deliverable_items"].wrapper);
			
			$(frm.fields_dict['receivable_items'].wrapper).html("")
			frm.receivable_items = new frappe.production.ui.Receivables(frm.fields_dict["receivable_items"].wrapper)
			
			if(frm.doc.process_name){
				val = await check_process(frm.doc.process_name,frm.doc.production_detail)
			}
			if(frm.doc.docstatus == 0 && frm.doc.item && val){
				frm.add_custom_button("Calculate Items", function(){
					frappe.call({
						method: 'production_api.production_api.doctype.work_order.work_order.get_lot_items',
						args: {
							lot: frm.doc.lot,
							process: frm.doc.process_name
						},
						callback: async function(r){
							let d = new frappe.ui.Dialog({
								title: 'Lot Items',
								fields: [
									{
										fieldtype: "HTML",
										fieldname: "lot_items_html"
									}
								],
								size:"large",
								primary_action(){
									frm.trigger("calculate_del_and_rec")
									d.hide()
								} 
							})
							frm.order_detail = new frappe.production.ui.WorkOrderItemView(d.fields_dict.lot_items_html.wrapper)
							await frm.order_detail.load_data(r.message)
							frm.order_detail.create_input_attributes()
							d.show()						
						}
					})
				})
			}
			if(frm.doc.__onload && frm.doc.__onload.deliverable_item_details) {
				frm.doc['deliverable_item_details'] = JSON.stringify(frm.doc.__onload.deliverable_item_details);
				frm.deliverable_items.load_data(frm.doc.__onload.deliverable_item_details);
			}
			else{
				frm.deliverable_items.load_data([])
			}
			frm.deliverable_items.update_status(val);
			
			if(frm.doc.__onload && frm.doc.__onload.receivable_item_details) {
				frm.doc['receivable_item_details'] = JSON.stringify(frm.doc.__onload.receivable_item_details);
				frm.receivable_items.load_data(frm.doc.__onload.receivable_item_details);
			}
			else{
				frm.deliverable_items.load_data([])
			}
			frm.receivable_items.update_status(val)
			
			frappe.production.ui.eventBus.$on("wo_updated", e => {
				frm.dirty();
			})
		}
	},
	calculate_del_and_rec(frm){
		let items = frm.order_detail.get_work_order_items()
		frappe.call({
			method:'production_api.production_api.doctype.work_order.work_order.get_deliverable_receivable',
			args: {
				lot: frm.doc.lot,
				process: frm.doc.process_name,
				items: items,
				doc_name: frm.doc.name,
			},
		})
	},
    validate(frm) {
		if(val == null && !frm.is_new()){
			let deliverables = frm.deliverable_items.get_deliverables_data();
			frm.doc['deliverable_item_details'] = JSON.stringify(deliverables);
			
			let receivables = frm.receivable_items.get_receivables_data();
			frm.doc['receivable_item_details'] = JSON.stringify(receivables);
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

async function check_process(process, ipd){
	return new Promise((resolve, reject) => {
        frappe.call({
            method:"production_api.production_api.doctype.work_order.work_order.check_process",
			args: {
				process: process,
				ipd:ipd,
			},
            callback: function(r) {
                resolve(r.message); 
            },
        });
    });
}
