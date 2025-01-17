// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Goods Received Note', {
	setup: function(frm) {
		frm.set_query('against_id', function(doc) {
			let filters = {
				'docstatus': 1,
			}
			if (doc.supplier) {
				filters['supplier'] = doc.supplier
			}
			if (doc.against == 'Purchase Order') {
				filters['status'] = ['in', ['Ordered', 'Partially Delivered', 'Overdue', 'Partially Cancelled']]
				filters['open_status'] = 'Open'
			}
			return{
				filters: filters
			}
		});

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

		frm.set_query('delivery_address', function(doc) {
			if(!doc.delivery_location) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'delivery_location', doc.name))]));
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
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'delivery_location', doc.name))]));
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
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'supplier', doc.name))]));
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
	refresh: function(frm) {
		$(frm.fields_dict['item_html'].wrapper).html("");
		frm.itemEditor = new frappe.production.ui.GRNItem(frm.fields_dict["item_html"].wrapper);
		frm.itemEditor.load_data({
			supplier: frm.doc.supplier,
			against: frm.doc.against,
			against_id: frm.doc.against_id
		}, true);
		if(frm.doc.__onload && frm.doc.__onload.item_details) {
			frm.doc['item_details'] = JSON.stringify(frm.doc.__onload.item_details);
			if(frm.doc.__onload && frm.doc.__onload.item_pending_details){
				frm.doc['item_pending_details'] = JSON.stringify(frm.doc.__onload.item_pending_details)
				frm.itemEditor.load_data({
					items: frm.doc.__onload.item_details,
					pending_items: frm.doc.__onload.item_pending_details
				}, true);	
			}
			else{
				frm.itemEditor.load_data({
					items: frm.doc.__onload.item_details,
				}, true);
			}
			
		} 
		else if (frm.doc.item_details) {
			if(frm.doc.item_pending_details){
				frm.itemEditor.load_data({
					items: JSON.parse(frm.doc.item_details),
					pending_items:JSON.parse(frm.doc.item_pending_details)
				}, true);
			}
			else{
				frm.itemEditor.load_data({
					items: JSON.parse(frm.doc.item_details),
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
	},

	save_item_details: function(frm) {
		if(frm.itemEditor){
			let items = frm.itemEditor.get_items();
			if(items && items.length > 0 && frm.doc.against == "Work Order") {
				frm.doc['item_details'] = JSON.stringify(items[0]);
				frm.doc['item_pending_details'] = JSON.stringify(items[1])
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
			if (!frm.doc.item_details) {
				frappe.throw(__('Add Items to continue'));
			}
		}
		else {
			frappe.throw(__('Please refresh and try again.'));
		}
	},


	supplier: function(frm) {
		if (frm.doc.supplier) {
			frappe.production.ui.eventBus.$emit("update_grn_details", {supplier: frm.doc.supplier})
		}
		if (frm.doc.supplier) {
			frappe.call({
				method: "production_api.production_api.doctype.supplier.supplier.get_primary_address",
				args: {"supplier": frm.doc.supplier},
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

	delivery_location: function(frm) {
		if (frm.doc.delivery_location) {
			frappe.call({
				method: "production_api.production_api.doctype.supplier.supplier.get_primary_address",
				args: {"supplier": frm.doc.delivery_location},
				callback: function(r) {
					if (r.message) {
						frm.set_value('delivery_address', r.message)
					} else {
						frm.set_value('delivery_address', '')
					}
				}
			})
		}
	},

	against: function(frm) {
		frappe.production.ui.eventBus.$emit("update_grn_details", {against: frm.doc.against})
	},

	against_id: function(frm) {
		frappe.production.ui.eventBus.$emit("update_grn_details", {against_id: frm.doc.against_id})
		if (frm.doc.against_id) {
			frappe.db.get_doc(frm.doc.against, frm.doc.against_id)
				.then(doc => {
					frm.set_value('supplier', doc.supplier);
					frm.set_value('delivery_location', doc.default_delivery_location);
				})
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
				args: {"address_dict": frm.doc['supplier_address'] },
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
				args: {"address_dict": frm.doc['delivery_address'] },
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
				args: {"address_dict": frm.doc['billing_address'] },
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
				args: {contact: frm.doc.contact_person },
				callback: function(r) {
					if (r.message)
						frm.set_value(r.message);
				}
			})
		}
	},
});
