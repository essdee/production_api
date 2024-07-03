// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Work Order", {
	refresh(frm) {
		if(frm.doc.start_date){
			frm.add_custom_button('End Date', ()=>{
				frappe.call({
					method: 'production_api.production_api.doctype.work_order.work_order.check_delivered_and_received',
					args: {
						doc_name: frm.doc.name,
					},
					callback: function(r){
						if(r.message[0] == false){
							if(r.message[1]=='Deliverable'){
								frappe.msgprint('Not all items are delivered')
							}
							else{
								frappe.msgprint('Not all items are received')
							}
						}
					}

				})
			})
		}
		if(frm.doc.docstatus == 1){
			frm.add_custom_button('Change Delievery Date',()=>{
				var d = new frappe.ui.Dialog({
					title : 'Change Deleivery Date',
					fields : [
						{
							fieldname : 'date',
							fieldtype : 'Date',
							label : "Delivery Date",
							default : frm.doc.expected_delivery_date,
						},
						{
							fieldname : 'reason',
							fieldtype : 'Data',
							label : 'Reason'
						}
					],
					primary_action_label : "Submit",
					primary_action(values){
						frappe.call({
							method : 'production_api.production_api.doctype.work_order.work_order.add_comment',
							args : {
								doc_name : frm.doc.name,
								date : values.date,
								reason : values.reason,
							}

						})
						d.hide()
					}
				})
				d.show()
			})
			frm.add_custom_button('Close', ()=> {
				let receivables = frm.doc.receivables
				for(let i=0;i<receivables.length; i++){
					if(receivables[i].pending_qty != 0){
						frappe.msgprint(`Not all ${receivables[i].item_variant} was received`)
						return
					}
				}
			})
		}
		frm.set_query('ppo',()=> {
			return {
				filters : {
					docstatus : 1
				}
			}
		})
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
