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
		frm.set_query('work_order',(doc) => {
            let fil = {
				"docstatus" : 1,
				"is_delivered" : 0,
				"open_status":"Open",
				"is_rework": doc.is_rework
			}
			if (doc.supplier){
				fil['supplier'] = doc.supplier
			}	
			return {
                filters : fil
            }
        })
    },
    refresh(frm){
		$(".layout-side-section").css("display", "None");
		frm.page.btn_secondary.hide()
        $(frm.fields_dict['deliverable_items'].wrapper).html("")
		frm.calculated = false
		if(frm.is_new()){
			if(frm.doc.work_order){
				frm.trigger("work_order")
			}
			else{
				frm.deliverable_items = new frappe.production.ui.Delivery_Challan(frm.fields_dict['deliverable_items'].wrapper)
				frm.deliverable_items.update_status();
			}
		}
		else {
			if(frm.doc.__onload && frm.doc.__onload.deliverable_item_details) {
				frm.doc['deliverable_item_details'] = JSON.stringify(frm.doc.__onload.deliverable_item_details);
				frm.deliverable_items = new frappe.production.ui.Delivery_Challan(frm.fields_dict['deliverable_items'].wrapper)
				frm.deliverable_items.load_data(frm.doc.__onload.deliverable_item_details)
				frm.deliverable_items.update_status();
			}
			if(frm.doc.docstatus == 0 && !frm.doc.is_rework){
				frm.add_custom_button("Calculate", function(){
					frappe.call({
						method: "production_api.production_api.doctype.delivery_challan.delivery_challan.get_calculated_items",
						args: {
							doc_name: frm.doc.name,
							work_order: frm.doc.work_order,
						},
						callback: async function (r) {
							let d = new frappe.ui.Dialog({
								size: "extra-large",
								fields: [
									{
										fieldname: "calculated_items_html",
										fieldtype: "HTML",
									},
								],
								primary_action() {
									frm.trigger("calculate_deliverables")
									d.hide()
								},
							});
							frm.calculate_deliverables = new frappe.production.ui.WorkOrderItemView(d.fields_dict.calculated_items_html.wrapper)
							await frm.calculate_deliverables.load_data(r.message)
							frm.calculate_deliverables.create_input_attributes()
							d.show()						
						},
					});
				})
			}
		}

		if(frm.doc.docstatus == 1){
			if(!frm.doc.transfer_complete && frm.doc.is_internal_unit){
				frm.add_custom_button("Complete Transfer", ()=> {
					frappe.call({
						method:"production_api.production_api.doctype.delivery_challan.delivery_challan.construct_stock_entry_details",
						args: {
							doc_name : frm.doc.name,
						},
						freeze:true,
						freeze_message:"Creating Stock Entry",
						callback: function(r){
							frappe.set_route("Form","Stock Entry",r.message)
						}
					})
				})
			}
			frm.add_custom_button("Cancel", ()=> {
				frm._cancel()
			})
			frm.add_custom_button("Return", ()=> {
				let return_items = null
				frappe.call({
					method:"production_api.production_api.doctype.delivery_challan.delivery_challan.get_return_delivery_items",
					args: {
						doc_name : frm.doc.name,
					},
					freeze:true,
					callback: function(r){
						let d = new frappe.ui.Dialog({
							title: __("Return Items"),
							fields: [
								{
									"fieldname": 'return_pop_up_html',
									"fieldtype": 'HTML',
								},
							],
							size: "extra-large",
							primary_action_label: __("Return"),
							primary_action: function(){
								let returned_items = return_items.get_data()
								d.hide()
								frappe.call({
									method: "production_api.production_api.doctype.delivery_challan.delivery_challan.create_return_grn",
									args: {
										doc_name: frm.doc.name,
										items: returned_items,
										ipd: frm.doc.production_detail,
									},
									callback: function(r){
										frappe.set_route("Form", "Goods Received Note", r.message)
									}
								})
							}
						})
						d.fields_dict['return_pop_up_html'].$wrapper.html("")
						return_items = new frappe.production.ui.ReturnItemsPopUp(d.fields_dict['return_pop_up_html'].wrapper)
						return_items.load_data(r.message)
						d.show()
					}
				})
			})
		}
    },
	work_order:function(frm) {
        frm.doc.items = [];
        $(frm.fields_dict['deliverable_items'].wrapper).html("")
        if (! frm.doc.work_order){
            return;
        }
        else{
			if(frm.is_new() && sessionStorage.getItem("cut_panel_dc")){
				frm.deliverable_items = new frappe.production.ui.Delivery_Challan(frm.fields_dict['deliverable_items'].wrapper)
				frm.deliverable_items.load_data(JSON.parse(sessionStorage.getItem("delivery_challan_onload_data")))
			}
			else{
				frappe.call({
					method:"production_api.production_api.doctype.delivery_challan.delivery_challan.get_deliverables",
					args:{
						"work_order": frm.doc.work_order,
					},
					callback: function(response){
						if(response.message){
							frm.deliverable_items = new frappe.production.ui.Delivery_Challan(frm.fields_dict['deliverable_items'].wrapper)
							frm.deliverable_items.load_data(response.message.items)
							frm.set_value('supplier',response.message.supplier)
							frm.set_value('supplier_address',response.message.supplier_address)
						}
					}
				})
			}
        }
	},
	calculate_deliverables(frm){
		let items = frm.calculate_deliverables.get_work_order_items()
		frappe.call({
			method:'production_api.production_api.doctype.delivery_challan.delivery_challan.get_calculated_deliverables',
			args: {
				items: items,
				wo_name: frm.doc.work_order,
				doc_name: frm.doc.name,
				deliverable:true
			},
			freeze:true,
			freeze_message: __("Calculate Deliverables..."),
			callback: function(r){
				frm.calculated = true
				frm.reload_doc()
			}
		})
	},
    validate: function(frm){
		if(!frm.calculated){
			let deliverables = frm.deliverable_items.get_data()
        	frm.doc['deliverable_item_details'] = JSON.stringify(deliverables)
		}
		else{
			frm.doc['deliverable_item_details'] = null
		}
		if(sessionStorage.getItem("cut_panel_dc")){
			sessionStorage.removeItem("cut_panel_dc")
			sessionStorage.removeItem("delivery_challan_onload_data")
		}
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
					else{
						frm.set_value("from_address","")
					}
				}
			})
		}
		else{
			frm.set_value("from_address","")
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
					else{
						frm.set_value('from_address_details', '');
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
					else{
						frm.set_value('supplier_address_details', '');
					}
				}
			})
		} 
		else {
			frm.set_value('supplier_address_details', '');
		}
	},
});
