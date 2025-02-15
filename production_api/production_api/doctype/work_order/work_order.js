// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt
frappe.ui.form.on("Work Order", {
	setup (frm){
		frm.set_query('supplier_address', function(doc) {
			if (!doc.supplier) {
				frappe.throw(__("Please set {0}", [__(frappe.meta.get_label(doc.doctype, 'supplier', doc.name))]));
			}
			return {
				query: 'frappe.contacts.doctype.address.address.address_query',
				filters: {
					link_doctype: 'Supplier',
					link_name: doc.supplier
				}
			};
		});
		
		frm.set_query('delivery_address', function(doc) {
			if(!doc.delivery_location) {
				frappe.throw(__("Please set {0}",[__(frappe.meta.get_label(doc.doctype, 'delivery_location', doc.name))]));
			}
			return {
				query: 'frappe.contacts.doctype.address.address.address_query',
				filters: {
					link_doctype: 'Supplier',
					link_name: doc.delivery_location
				}
			};
		});
		frm.set_query("parent_wo",function(doc){
			return{
				filters: {
					"name" : ["!=",doc.name] 
				}
			}
		})
	},
	async refresh(frm) {
		frm.val = null
		if(frm.is_new()){
			hide_field(["deliverable_items", "receivable_items"]);
		}
		else{
			unhide_field(["deliverable_items", "receivable_items"]);
			$(frm.fields_dict['deliverable_items'].wrapper).html("")
			frm.deliverable_items = new frappe.production.ui.Deliverables(frm.fields_dict["deliverable_items"].wrapper);
			
			$(frm.fields_dict['receivable_items'].wrapper).html("")
			frm.receivable_items = new frappe.production.ui.Receivables(frm.fields_dict["receivable_items"].wrapper)
			if(frm.doc.is_rework){
				frm.val = true
			}
			if(frm.doc.docstatus == 0 && frm.doc.item && !frm.doc.is_rework){
				frm.add_custom_button("Calculate Items", function(){
					if(frm.is_dirty()){
						frappe.msgprint("Save the file before calculate")
						return
					}
					frappe.call({
						method: 'production_api.production_api.doctype.work_order.work_order.get_lot_items',
						args: {
							lot: frm.doc.lot,
							doc_name : frm.doc.name,
							process: frm.doc.process_name,
						},
						callback: async function(r){
							let d = new frappe.ui.Dialog({
								title: 'Lot Items',
								fields: [
									{fieldtype: "HTML",fieldname: "lot_items_html"}
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
			if(frm.doc.open_status == 'Open' && frm.doc.docstatus == 1){
				frm.add_custom_button('Change Delivery Date',()=>{
					var d = new frappe.ui.Dialog({
						title : 'Change Delivery Date',
						fields : [
							{fieldname :'date',fieldtype :'Date',label :"Delivery Date","default" :frm.doc.expected_delivery_date,"reqd" :1},
							{fieldname : 'reason',fieldtype : 'Data',label : 'Reason',reqd : 1}
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
					let data = []
					for(let i = 0 ; i < receivables.length ; i++){
						let row = receivables[i];
						if (row.pending_quantity > 0){
							data.push(
								{"item_variant":row.item_variant,"qty":row.qty,"pending_qty":row.pending_quantity}
							)
						}
					}
					let d = new frappe.ui.Dialog({
						title:"Pending quantity of receivables",
						fields : [
							{
								fieldtype:'Table',fieldname: "receivable_details",label:"Receivables",readonly:true,
								cannot_add_rows: true,cannot_delete_rows:true,in_place_edit: false,data : data,
								fields:[
									{fieldname: "item_variant", fieldtype: "Link", options: "Item Variant", in_list_view: true, read_only: true, label: "Item"},
									{fieldname: "qty", fieldtype: "Float", in_list_view: true, label: "Quantity", read_only: true},
									{fieldname: "pending_qty", fieldtype: "Float", in_list_view: true, label: "Pending Quantity", read_only: true}
								]
							}
						],
						primary_action_label: "Close Work Order",
						primary_action(){
							d.hide()
							let x = new frappe.ui.Dialog({
								title: "Are you sure want to close this work order",
								primary_action_label:'Yes',
								secondary_action_label:"No",
								primary_action:() => {
									x.hide();
									frappe.call({
										method:"production_api.production_api.doctype.work_order.work_order.update_stock",
										args : {
											work_order: frm.doc.name,
										},
										callback: function(){
											frm.refresh()
										}
									})
								},
								secondary_action:()=>{
									x.hide()
								}
							})
							x.show()
						}
					})
					d.show()
				})
				frm.add_custom_button(__('Make DC'), function() {
					let x = frappe.model.get_new_doc('Delivery Challan')
					x.work_order = frm.doc.name
					x.naming_series = "DC-"
					x.posting_date = frappe.datetime.nowdate()
					x.posting_time = new Date().toTimeString().split(' ')[0]
					frappe.set_route("Form",x.doctype, x.name);
				}, __("Create"));
				frm.add_custom_button(__('Make GRN'), function() {
					let y = frappe.model.get_new_doc('Goods Received Note')
					y.against = "Work Order"
					y.naming_series = "GRN-"
					y.against_id = frm.doc.name
					y.supplier = frm.doc.supplier
					y.supplier_address = frm.doc.supplier_address
					y.posting_date = frappe.datetime.nowdate()
					y.posting_time = new Date().toTimeString().split(' ')[0]
					frappe.set_route("Form",y.doctype, y.name);
				}, __("Create"));
			}
			if(frm.doc.__onload && frm.doc.__onload.deliverable_item_details) {
				frm.doc['deliverable_item_details'] = JSON.stringify(frm.doc.__onload.deliverable_item_details);
				frm.deliverable_items.load_data(frm.doc.__onload.deliverable_item_details);
			}
			else{
				frm.deliverable_items.load_data([])
			}
			frm.deliverable_items.update_status(frm.val);
			
			if(frm.doc.__onload && frm.doc.__onload.receivable_item_details) {
				frm.doc['receivable_item_details'] = JSON.stringify(frm.doc.__onload.receivable_item_details);
				frm.receivable_items.load_data(frm.doc.__onload.receivable_item_details);
			}
			else{
				frm.deliverable_items.load_data([])
			}
			frm.receivable_items.update_status(true)
			
			frappe.production.ui.eventBus.$on("wo_updated", e => {
				frm.dirty();
			})
		}
	},
	calculate_pieces(frm){
		frappe.call({
			method:"production_api.production_api.doctype.work_order.work_order.calculate_completed_pieces",
			args: {
				doc_name: frm.doc.name,
			}
		})
	},
	calculate_del_and_rec(frm){
		let items = frm.order_detail.get_work_order_items()
		frappe.call({
			method:'production_api.production_api.doctype.work_order.work_order.get_deliverable_receivable',
			args: {
				items: items,
				doc_name: frm.doc.name,
			},
			freeze:true,
			freeze_message: __("Calculate Deliverables and Receivables..."),
		})
	},
    validate(frm) {
		if(frm.val == null && !frm.is_new()){
			let deliverables = frm.deliverable_items.get_deliverables_data();
			frm.doc['deliverable_item_details'] = JSON.stringify(deliverables);
			
			let receivables = frm.receivable_items.get_receivables_data();
			frm.doc['receivable_item_details'] = JSON.stringify(receivables);
		}
    },
    supplier:async function(frm) {
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
					else{
						frm.set_value('supplier_address', '')
					}
				}
			})
		}
		else{
			frm.set_value('supplier_address', '')
		}
	},
	delivery_location: function(frm) {
		if (frm.doc.delivery_location) {
			frappe.production.ui.eventBus.$emit("supplier_updated", frm.doc.delivery_location)
		}
		if (frm.doc.delivery_location) {
			frappe.call({
				method: "production_api.production_api.doctype.supplier.supplier.get_primary_address",
				args: {
					"supplier": frm.doc.delivery_location
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('delivery_address', r.message)
					}
					else{
						frm.set_value('delivery_address', '')
					}
				}
			})
		}
		else{
			frm.set_value('delivery_address', '')
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
					else{
						frm.set_value('supplier_address_details', '')
					}
				}
			})
		} 
		else{
			frm.set_value('supplier_address_details', '')
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
