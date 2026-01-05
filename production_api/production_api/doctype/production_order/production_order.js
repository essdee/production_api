// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Production Order", {
    setup(frm){
        frm.set_query("production_term", (doc)=> {
            return {
                filters : {
                    "docstatus": 1
                }
            }
        })
    },
    refresh(frm) {
        frm.fields_dict["details_html"].$wrapper.html("")
        if (!frm.is_new()) {
            frm.packed_item = new frappe.production.ui.ProductionOrder(frm.fields_dict["details_html"].wrapper);
            if (frm.doc.__onload && frm.doc.__onload.ordered_details) {
                frm.doc['item_details'] = JSON.stringify(frm.doc.__onload.ordered_details);
                frm.packed_item.load_data(frm.doc.__onload.ordered_details);
            }
        }
        if (frm.doc.docstatus == 1) {
            frm.add_custom_button("Update Price", () => {
                let d = new frappe.ui.Dialog({
                    title: "Update Price",
                    size: 'extra-large',
                    fields: [
                        {
                            fieldname: "price_html",
                            fieldtype: "HTML",
                        }
                    ],
                    primary_action: function () {
                        let res = frm.pop_up.get_data()
                        frappe.call({
                            method: "production_api.production_api.doctype.production_order.production_order.update_price",
                            args: {
                                production_order: frm.doc.name,
                                item_details: res
                            },
                            callback: function (response) {
                                frm.refresh()
                            }
                        })
                        d.hide();
                    }
                })
                frm.pop_up = new frappe.production.ui.UpdatePrice(d.fields_dict.price_html.$wrapper)
                if (frm.doc.__onload && frm.doc.__onload.items) {
                    frm.doc['item_details'] = JSON.stringify(frm.doc.__onload.items);
                    frm.pop_up.load_data(frm.doc.__onload.items);
                }
                d.show();
            })
            frm.add_custom_button("Create Lot", () => {
                let d = new frappe.ui.Dialog({
                    title: "Create Lot",
                    fields: [
                        {
                            fieldname: "lot_name",
                            fieldtype: "Data",
                            label: "Lot Name",
                            reqd: 1,
                        },
                    ],
                    primary_action: function () {
                        let values = d.get_values();
                        if (!values) return;

                        frappe.call({
                            method: "production_api.production_api.doctype.production_order.production_order.create_lot",
                            args: {
                                production_order: frm.doc.name,
                                lot_name: values.lot_name
                            },
                            callback: function (response) {
                                d.hide();
                                frappe.show_alert({
                                    message: __("Lot {0} created successfully", [values.lot_name]),
                                    indicator: "green"
                                });
                                frm.set_route("Form", "Lot", response.message);
                            }
                        });
                    }
                });
                d.show();
            })
            frm.add_custom_button("Link Lot", () => {
                let d = new frappe.ui.Dialog({
                    title: "Link Lot",
                    fields: [
                        {
                            fieldname: "lot_name",
                            fieldtype: "Link",
                            label: "Lot Name",
                            reqd: 1,
                            options: "Lot"
                        },
                    ],
                    primary_action: function () {
                        let values = d.get_values();
                        if (!values) return;

                        frappe.call({
                            method: "production_api.production_api.doctype.production_order.production_order.link_lot",
                            args: {
                                production_order: frm.doc.name,
                                lot_name: values.lot_name
                            },
                            callback: function (response) {
                                d.hide();
                                frappe.show_alert({
                                    message: __("Lot {0} linked successfully", [values.lot_name]),
                                    indicator: "green"
                                });
                                frm.set_route("Form", "Lot", values.lot_name);
                            }
                        });
                    }
                });
                d.show();
            })
        }
    },
    validate(frm) {
        if (!frm.is_new()) {
            if (frm.packed_item) {
                let items = frm.packed_item.get_data();
                frm.doc['item_details'] = JSON.stringify(items);
            }
            else {
                frappe.throw(__('Please refresh and try again.'));
            }
        }
        frappe.call({
            method: "production_api.production_api.doctype.production_order.production_order.get_primary_values",
            args: {
                item: cur_frm.doc.item
            },
            callback: function (response) {
                if (cur_frm.doc.docstatus != 0) {
                    disables.value = true
                }
                primary_values.value = response.message || [];
                primary_values.value.forEach(value => {
                    if (!(value in box_qty.value)) {
                        box_qty.value[value] = 0;
                    }
                });
            }
        })
    },
});
