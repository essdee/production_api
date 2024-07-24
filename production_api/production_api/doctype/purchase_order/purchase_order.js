// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Purchase Order', {
	setup: function(frm) {
		frm.set_query('default_delivery_location', function(doc) {
			return{
				filters: {
					is_company_location: doc.deliver_to_supplier ? 0 : 1,
				}
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
			if(!doc.default_delivery_location) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'default_delivery_location', doc.name))]));
			}

			return {
				query: 'frappe.contacts.doctype.address.address.address_query',
				filters: {
					link_doctype: 'Supplier',
					link_name: doc.default_delivery_location
				}
			};
		});

		frm.set_query('billing_address', function(doc) {
			if(!doc.default_delivery_location) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'default_delivery_location', doc.name))]));
			}

			return {
				query: 'frappe.contacts.doctype.address.address.address_query',
				filters: {
					link_doctype: 'Supplier',
					link_name: doc.default_delivery_location
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
		frm.itemEditor = new frappe.production.ui.PurchaseOrderItem(frm.fields_dict["item_html"].wrapper);
		if(frm.doc.__onload && frm.doc.__onload.item_details) {
			frm.doc['item_details'] = JSON.stringify(frm.doc.__onload.item_details);
			frm.itemEditor.load_data(frm.doc.__onload.item_details);
		} else {
			frm.itemEditor.load_data([]);
		}
		frm.itemEditor.update_status();
		frappe.production.ui.eventBus.$on("po_updated", e => {
			frm.dirty();
		})
		
		// Check if frappe.user_roles has role Purchase Manager 
		let is_purchase_manager = frappe.user.has_role('Purchase Manager');
		let is_purchase_user = frappe.user.has_role('Purchase User');
		if (frm.doc.docstatus == 1 && (is_purchase_manager || is_purchase_user)) {
			frm.page.btn_secondary.hide();
			// Add send notification button if the status is not closed or cancelled or partially cancelled
			let closed_statuses = ['Closed', 'Cancelled', 'Partially Cancelled']	
			if (!closed_statuses.includes(frm.doc.status)) {
				frm.add_custom_button(__('Send SMS'), function() {
					frappe.call({
						method: "production_api.production_api.util.send_notification",
						args: {
							"doctype": frm.doc.doctype,
							"docname": frm.doc.name,
							"channels": ['SMS'],
						},
						callback: function(r) {
							if (r.message) {
								console.log(r.message)
							}
						}
					})
				}, __("Send Notification"));
				frm.add_custom_button(__('Send Email'), function() {
					frappe.call({
						method: "production_api.production_api.util.send_notification",
						args: {
							"doctype": frm.doc.doctype,
							"docname": frm.doc.name,
							"channels": ['Email'],
						},
						callback: function(r) {
							if (r.message) {
								console.log(r.message)
							}
						}
					})
				}, __("Send Notification"));
				frm.add_custom_button(__('Copy Message'), function() {
					frappe.call({
						method: "production_api.production_api.util.get_notification_message",
						args: {
							"doctype": frm.doc.doctype,
							"docname": frm.doc.name,
						},
						callback: function(r) {
							if (r.message) {
								frappe.utils.copy_to_clipboard(r.message)
							}
						}
					})
				}, __("Send Notification"));
			}
			let update_status = ['Cancelled','Closed','Partially Cancelled','Delivered']
			if (!update_status.includes(frm.doc.status)) {
				frm.add_custom_button(__('Update Delivery Date'), function() {
					let dialog = new frappe.ui.Dialog({
						title: 'Update Delivery Date',
						fields: [
							{
								fieldname: "html_field",
								fieldtype: 'HTML',
							},
							{
								fieldname: 'comments',
								fieldtype: 'Small Text',
								label: 'Comments'
							}
						],
						primary_action_label: 'Save',
						primary_action :(values)=>{
							let items = popupDialog.get_items()
							dialog.hide()
							frappe.call({
								method: 'production_api.production_api.doctype.purchase_order.purchase_order.update_table',
								args: {
									doc_name: frm.doc.name,
									data: items,
									comment : values.comments
								}
							})
						},	 
					})
					let popupDialog = new frappe.production.ui.DateDialog(dialog.fields_dict['html_field'].wrapper, frm.doc.items);
					
					dialog.show();
					dialog.$wrapper.find('.modal-dialog').css("min-width",'max-content')

				})
			}
			if (frm.doc.status != 'Partially Cancelled' && frm.doc.open_status == 'Open') {
				frm.add_custom_button(__('Cancel'), function() {
					frappe.prompt({
						label: 'Reason',
						fieldname: 'reason',
						fieldtype: 'Data',
						reqd: 1
					}, (values) => {
						// console.log(values.reason);
						frappe.call({
							method: "production_api.production_api.doctype.purchase_order.purchase_order.cancel_purchase_order",
							args: {
								"purchase_order": frm.doc.name,
								"reason": values.reason
							},
							callback: function(r) {
								if (r.message) {
									console.log(r.message)
								}
							}
						})
					},
					'Reason for Cancellation',
					'Submit')
				});
			}

			if (frm.doc.open_status == 'Open') {
				frm.add_custom_button(__('Close'), function() {
					if (frm.is_dirty()) {
						frappe.throw(__("Please save the document before closing"));
					}
					frappe.confirm('Are you sure you want to close this Purchase Order?', function() {
						frappe.call({
							method: "production_api.production_api.doctype.purchase_order.purchase_order.close_purchase_order",
							args: {
								"purchase_order": frm.doc.name,
							},
							callback: function(r) {
								if (r.message) {
									console.log(r.message)
								}
							}
						})
					});
				});
			}

			frm.page.add_menu_item(__('Refresh Status'), function() {
				frappe.call({
					method: "production_api.production_api.doctype.purchase_order.purchase_order.refresh_status",
					args: {
						"purchase_order": frm.doc.name,
					},
					callback: function(r) {
						if (r.message) {
							console.log(r.message)
						}
					}
				})
			});
		}

		if (frm.doc.open_status == 'Closed') {
			frm.page.btn_secondary.hide();
			frm.page.btn_primary.hide();
			if (frappe.user.has_role("Purchase Manager")) {
				frm.page.add_menu_item(__('Reopen'), function() {
					frappe.call({
						method: "production_api.production_api.doctype.purchase_order.purchase_order.reopen_purchase_order",
						args: {
							"purchase_order": frm.doc.name,
						},
						callback: function(r) {
							if (r.message) {
								console.log(r.message)
							}
						}
					})
				});
			}
		}
	},

	validate: function(frm) {
		if(frm.itemEditor){
			let items = frm.itemEditor.get_items();
			if(items && items.length > 0) {
				frm.doc['item_details'] = JSON.stringify(items);
			}
			else {
				frappe.throw(__('Add Items to continue'));
			}
		}
		else {
			frappe.throw(__('Please refresh and try again.'));
		}
	},

	before_save: function(frm) {
		if(frm.itemEditor) {
			console.log(frm.itemEditor);
		}
	},

	supplier: function(frm) {
		if (frm.doc.supplier) {
			frappe.production.ui.eventBus.$emit("supplier_updated", frm.doc.supplier)
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

	default_delivery_location: function(frm) {
		if (frm.doc.default_delivery_location) {
			frappe.call({
				method: "production_api.production_api.doctype.supplier.supplier.get_primary_address",
				args: {"supplier": frm.doc.default_delivery_location},
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
		} else {
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
		} else {
			frm.set_value('delivery_address_display', '');
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
