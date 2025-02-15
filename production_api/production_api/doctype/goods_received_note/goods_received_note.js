// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt
frappe.ui.form.on('Goods Received Note', {
	setup: function(frm) {
		frm.set_query('against_id', function(doc) {
			let filters = {
				'docstatus': 1,
				"open_status":"Open"
			}
			if (doc.supplier) {
				filters['supplier'] = doc.supplier
			}
			if (doc.against == 'Purchase Order') {
				filters['status'] = ['in', ['Ordered', 'Partially Delivered', 'Overdue', 'Partially Cancelled']]
			}
			return{
				filters: filters
			}
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
		frm.set_query('billing_address', function(doc) {
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
		frm.set_query('contact_person', function(doc) {
			if(!doc.supplier) {
				frappe.throw(__("Please set {0}",[__(frappe.meta.get_label(doc.doctype, 'supplier', doc.name))]));
			}
			return {
				query: 'frappe.contacts.doctype.contact.contact.contact_query',
				filters: {
					link_doctype: 'Supplier',
					link_name: doc.supplier
				}
			};
		});
	},
	onload:async function(frm) {
		if (frm.is_new() && frm.doc.against_id && frm.doc.against == "Work Order") {
			await frm.trigger("against")
			frm.trigger("against_id")
		}
	},
	refresh: function(frm) {
		$(frm.fields_dict['item_html'].wrapper).html("");
		if(frm.doc.against == 'Purchase Order'){
			frm.itemEditor = new frappe.production.ui.GRNPurchaseOrder(frm.fields_dict["item_html"].wrapper);
			frm.itemEditor.load_data({
				supplier: frm.doc.supplier,
				against: frm.doc.against,
				against_id: frm.doc.against_id
			}, true);
			if(frm.doc.__onload && frm.doc.__onload.item_details) {
				frm.doc['item_details'] = JSON.stringify(frm.doc.__onload.item_details);
				frm.itemEditor.load_data({
					items: frm.doc.__onload.item_details,
				}, true);
			}
		}
		else{
			frm.page.btn_secondary.hide()
			frm.itemEditor = new frappe.production.ui.GRNWorkOrder(frm.fields_dict["item_html"].wrapper);
			frm.itemEditor.load_data({
				supplier: frm.doc.supplier,
				against: frm.doc.against,
				against_id: frm.doc.against_id
			}, true);
			if( frm.doc.__onload && frm.doc.__onload.item_details) {
				frm.doc['item_details'] = JSON.stringify(frm.doc.__onload.item_details);	
				frm.itemEditor.load_data({
					items: frm.doc.__onload.item_details,
				}, true);	
			}
		}
		frm.itemEditor.update_status();
		frappe.production.ui.eventBus.$on("grn_updated", e => {
			frm.dirty();
			frm.events.save_item_details(frm);
		})
		if (frm.doc.docstatus == 0) {
			var print_menu = $(".dropdown-menu > li:contains('Print')");
			if (print_menu.length > 0){
				print_menu[0].parentElement.removeChild(print_menu[0]);
			}
			var print_btn = $('[data-original-title="Print"]');
			if(print_btn.length > 0){
				print_btn[0].parentElement.removeChild(print_btn[0]);
			}
		}
		if(frm.doc.against == 'Work Order' && frm.doc.docstatus == 0 && !frm.is_new()){
			frm.add_custom_button("Calculate", function(){
				frappe.call({
					method: "production_api.production_api.doctype.delivery_challan.delivery_challan.get_calculated_items",
					args: {
						doc_name: frm.doc.name,
						work_order: frm.doc.against_id,
					},
					callback: async function (r) {
						let d = new frappe.ui.Dialog({
							size: "large",
							fields: [
								{
									fieldname: "received_type",
									fieldtype: "Link",
									options: "GRN Item Type",
									label:"Received Type",
									reqd: true
								},
								{
									fieldname: "calculated_items_html",
									fieldtype: "HTML",
								},
							],
							primary_action(values) {
								calculate_receivables(frm,values.received_type)
								d.hide()
							},
						});
						frm.calculate_receivables = new frappe.production.ui.WorkOrderItemView(d.fields_dict.calculated_items_html.wrapper)
						await frm.calculate_receivables.load_data(r.message)
						frm.calculate_receivables.create_input_attributes()
						d.show()						
					},
				});
			})
		}
		if(!frm.is_new()){
			if(frm.doc.is_manual_entry){
				frm.grn_consumed = new frappe.production.ui.GRNConsumed(frm.fields_dict['grn_consumed_html'].wrapper)
				if(frm.doc.__onload && frm.doc.__onload.consumed_items){
					frm.doc['grn_consumed_items'] = JSON.stringify(frm.doc.__onload.consumed_items)
					frm.grn_consumed.load_data(frm.doc.__onload.consumed_items)
				}
				else{
					frm.grn_consumed.load_data([])
				}
				frm.grn_consumed.update_status()
			}
		}
		frappe.production.ui.eventBus.$on("grn_updated", e => {
			frm.dirty();
		})
		if(frm.doc.docstatus == 1 && frm.doc.against == "Work Order" && frm.doc.is_internal_unit && !frm.doc.transfer_complete){
			frm.add_custom_button("Transfer Complete", ()=> {
				frappe.call({
					method: "production_api.production_api.doctype.goods_received_note.goods_received_note.construct_stock_entry_data",
					args : {
						doc_name: frm.doc.name,
					},
					freeze:true,
					freeze_message:"Creating Stock Entry",
					callback: function(r){
						frappe.set_route("Form","Stock Entry",r.message)
					}
				})
			})
		}
		if(frm.doc.docstatus == 1 && frm.doc.against == "Work Order"){
			frm.add_custom_button("Cancel", ()=> {
				frm._cancel()
			})
		}
		// if(frm.doc.docstatus == 1 && frm.doc.against == "Work Order" && frm.doc.rework_created == 0){
		// 	frm.add_custom_button("Create Rework",()=> {
		// 		let d =new frappe.ui.Dialog({
		// 			title : "Select the type of rework",
		// 			fields: [
		// 				{
		// 					"fieldname":"supplier_type",
		// 					"fieldtype":"Select",
		// 					"label":"Supplier Type",
		// 					"options":"Same Supplier\nDifferent Supplier",
		// 					"reqd":true,
		// 				},
		// 				{
		// 					"fieldname":"rework_type",
		// 					"fieldtype":"Select",
		// 					"label":"Rework Type",
		// 					"options":"No Cost\nNet Cost Nil\nAdditional Cost",
		// 					"reqd":true,
		// 				},
		// 			],
		// 			primary_action(values){
		// 				if(values.supplier_type == 'Different Supplier'){
		// 					d.hide()
		// 					let dialog = new frappe.ui.Dialog({
		// 						title:"Select Supplier",
		// 						fields: [
		// 							{
		// 								"fieldname":"supplier",
		// 								"fieldtype":"Link",
		// 								"options":"Supplier",
		// 								"label":"Supplier",
		// 							},
		// 							{
		// 								"fieldname":"supplier_address",
		// 								"fieldtype":"Link",
		// 								"options":"Address",
		// 								"label":"Supplier Address",
		// 							}
		// 						],
		// 						primary_action(val){
		// 							dialog.hide()
		// 							make_rework(frm, val.supplier, val.supplier_address, frm.doc.delivery_address, values.rework_type, values.supplier_type)
		// 						}
		// 					})
		// 					dialog.show()
		// 				}
		// 				else{
		// 					d.hide()
		// 					make_rework(frm, frm.doc.supplier, frm.doc.supplier_address, frm.doc.delivery_address, values.rework_type, values.supplier_type)
		// 				}
		// 			}
		// 		})
		// 		d.show()
		// 	})
		// }
	},
	save_item_details: function(frm) {
		if(frm.itemEditor){
			let items = frm.itemEditor.get_items();
			if(items && items.length > 0 && frm.doc.against == "Work Order") {
				frm.doc['item_details'] = JSON.stringify(items[0]);
				frm.doc['is_edited'] = items[1]
			}
			else if(items && items.length > 0 && frm.doc.against == "Purchase Order"){
				frm.doc['item_details'] = JSON.stringify(items);
			}
			else {
				frm.doc['item_details'] = null;
			}
		}
	},
	validate: function(frm) {
		if(frm.itemEditor){
			frm.events.save_item_details(frm);
		}
		else {
			frappe.throw(__('Please refresh and try again.'));
		}
		if(frm.grn_consumed){
			let items = frm.grn_consumed.get_deliverables_data();
			if(items){
				frm.doc['consumed_item_details'] = JSON.stringify(items)
			}
			else{
				frm.doc['consumed_item_details'] = null
			}
		}
	},
	supplier: function(frm) {
		if (frm.doc.supplier) {
			if(frm.doc.against == 'Purchase Order'){
				frappe.production.ui.eventBus.$emit("update_grn_details", {against: frm.doc.against})
			}
			else{
				frappe.production.ui.eventBus.$emit("update_grn_work_details", {against: frm.doc.against})
			}
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
			frappe.call({
				method: "production_api.production_api.doctype.supplier.supplier.get_primary_address",
				args: {
					"supplier": frm.doc.delivery_location
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('delivery_address', r.message)
					} 
					else {
						frm.set_value('delivery_address', '')
					}
				}
			})
		}
		else{
			frm.set_value('delivery_address', '')
		}
	},
	against: function(frm) {
		frm.refresh()
		if(frm.doc.against == 'Purchase Order'){
			frappe.production.ui.eventBus.$emit("update_grn_details", {against: frm.doc.against})
		}
		else{
			frappe.production.ui.eventBus.$emit("update_grn_work_details", {against: frm.doc.against})
		}
		
	},
	against_id: function(frm) {
		if(frm.doc.against == 'Purchase Order'){
			frappe.production.ui.eventBus.$emit("update_grn_details", {against_id: frm.doc.against_id})
		}
		else{
			frappe.production.ui.eventBus.$emit("update_grn_work_details", {against_id: frm.doc.against_id})
		}
		if (frm.doc.against_id) {
			if(frm.doc.against == 'Purchase Order'){
				frappe.db.get_doc(frm.doc.against, frm.doc.against_id).then(doc => {
					frm.set_value('supplier', doc.supplier);
					frm.set_value('delivery_location', doc.default_delivery_location);
				})
			}
			else{
				frappe.db.get_doc(frm.doc.against, frm.doc.against_id).then(doc => {
					frm.set_value('supplier', doc.supplier);
					frm.set_value('supplier_address', doc.supplier_address);
				})
			}
		} 
		else {
			frm.set_value('supplier', '');
			frm.set_value('delivery_location', '');
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
						frm.set_value('supplier_address_display', r.message)
					}
				}
			})
		} 
		else {
			frm.set_value('supplier_address_display', '');
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
						frm.set_value('delivery_address_display', r.message)
					}
				}
			})
		} 
		else {
			frm.set_value('delivery_address_display', '');
		}
	},
	billing_address: function(frm) {
		if (frm.doc['billing_address']) {
			frappe.call({
				method: "frappe.contacts.doctype.address.address.get_address_display",
				args: {
					"address_dict": frm.doc['billing_address'] 
				},
				callback: function(r) {
					if (r.message) {
						frm.set_value('billing_address_display', r.message)
					}
				}
			})
		} 
		else {
			frm.set_value('billing_address_display', '');
		}
	},
	contact_person: function(frm) {
		if (frm.doc["contact_person"]) {
			frappe.call({
				method: "frappe.contacts.doctype.contact.contact.get_contact_details",
				args: {
					contact: frm.doc.contact_person 
				},
				callback: function(r) {
					if (r.message){
						frm.set_value(r.message);
					}
				}
			})
		}
	},
});

function make_rework(frm, supplier, supplier_address, delivery_address, rework_type, supplier_type){
	frappe.call({
		method:"production_api.production_api.doctype.goods_received_note.goods_received_note.get_grn_rework_items",
		args: {
			doc_name:frm.doc.name,
			supplier:supplier,
			supplier_address: supplier_address,
			delivery_address: delivery_address,
			rework_type:rework_type,
			supplier_type: supplier_type,
		},
		callback: function(r){
			if(r.message){
				frappe.set_route("Form","Work Order", r.message);
			}
			else{
				frappe.msgprint("There is no mistake items are received")
			}
		}
	})
}

function calculate_receivables(frm, received_type){
	let items = frm.calculate_receivables.get_work_order_items()
	frappe.call({
		method:'production_api.production_api.doctype.goods_received_note.goods_received_note.get_receivables',
		args: {
			items: items,
			doc_name: frm.doc.name,
			wo_name: frm.doc.against_id,
			receivable:true
		},
		freeze:true,
		freeze_message: __("Calculate Deliverables..."),
		callback: function(r){
			frappe.call({
				method:"production_api.production_api.doctype.goods_received_note.goods_received_note.update_calculated_receivables",
				args: {
					doc_name: frm.doc.name,
					receivables: r.message,
					received_type : received_type
				}
			})
		}
	})
}
