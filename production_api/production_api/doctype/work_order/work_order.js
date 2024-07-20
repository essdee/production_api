// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Work Order", {
	setup:function(frm){
		frm.set_query('supplier_address', function(doc) {
			if(!doc.supplier) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'supplier', doc.name))]));
			}

			return {
				query: 'frappe.contacts.doctype.address.address.address_query',
				filters: {
					link_doctype: 'Supplier',
					link_name: doc.supplier
				}
			};
		});
	},
	refresh(frm) {
		if(frm.doc.start_date && !frm.doc.end_date){
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
							reqd : 1,
						},
						{
							fieldname : 'reason',
							fieldtype : 'Data',
							label : 'Reason',
							reqd : 1,
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
			if(frm.doc.status == 'Open'){
				frm.add_custom_button('Close', ()=> {
					let receivables = frm.doc.receivables
					let d =new frappe.ui.Dialog({
						title:"Pending quantity of receivables",
						fields : [
							{
								'fieldtype':'HTML',
								'fieldname': "pending_qty",
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
										method:'production_api.production_api.doctype.work_order.work_order.make_close',
										args:{
											'docname': frm.doc.name,
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
					// style="border-collapse: collapse;border: 1px solid black;"
					d.fields_dict.pending_qty.$wrapper.html('');
					let html_content = `
						<table >
							<thead style="background-color : #D3D3D3;">
								<tr >
									<th style="width: 40%; font-size: 18px; text-align: center; ">Item</th>
									<th style="width: 15%; font-size: 18px; text-align: center; ">Quantity</th>
									<th style="width: 20%; font-size: 18px; text-align: center; ">Pending Qty</th>
								</tr>
							</thead>
							<tbody>
					`;
					for(let i = 0 ; i < receivables.length ; i++){
						let row = receivables[i];
						html_content += `
							<tr >
								<td style="font-size: 15px; text-align: center; ">${row.item_variant}</td>
								<td style="font-size: 15px; text-align: center; ">${row.qty}</td>
								<td style="font-size: 15px; text-align: center; ">${row.pending_quantity}</td>
							</tr>
						`;
					}
					html_content += `</tbody></table>`;
					d.fields_dict.pending_qty.$wrapper.append(html_content)
					d.show()
				})
			}
			frm.add_custom_button(__('Make GRN'), function() {
				let x = frappe.model.get_new_doc('Goods Received Note')
				x.against = "Work Order"
				x.naming_series = "GRN-"
				x.against_id = frm.doc.name
				x.supplier = frm.doc.supplier
				x.supplier_address = frm.doc.supplier_address
				x.supplier_address_display = frm.doc.supplier_address_details
				x.posting_date = frappe.datetime.nowdate()
				x.posting_time = new Date().toTimeString().split(' ')[0]
				frappe.set_route("Form",x.doctype, x.name);
			}, __("Create"));
	
			frm.add_custom_button(__('Make DC'), function() {
				let x = frappe.model.get_new_doc('Delivery Challan')
				x.work_order = frm.doc.name
				x.naming_series = "DC-"
				x.posting_date = frappe.datetime.nowdate()
				x.posting_time = new Date().toTimeString().split(' ')[0]
				frappe.set_route("Form",x.doctype, x.name);
			}, __("Create"));
		}

		frm.set_query('ppo',()=> {
			return {
				filters : {
					docstatus : 1
				}
			}
		})

		if(frm.doc.docstatus == 1){
			frm.set_df_property("expected_delivery_date","read_only" , true)
		}

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
