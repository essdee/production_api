// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Process Cost", {
	setup: function(frm) {
        frm.set_query('attribute', function(doc) {
            if(!doc.lot) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'lot', doc.name))]));
			}
            if(!doc.process_name){
                frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'process_name', doc.name))]));
            }
			return {
				query: 'production_api.production_api.doctype.process_cost.process_cost.get_item_attributes',
				filters: {
					item: doc.item,
                    lot: doc.lot,
                    process: doc.process_name
				}
			};
		});
        frm.set_query('attribute_value', 'process_cost_values', (doc) => {
            if(!doc.item) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'item', doc.name))]));
			}
            if(!doc.attribute) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'attribute', doc.name))]));
			}
			return {
				query: 'production_api.production_api.doctype.item.item.get_item_attribute_values',
				filters: {
					item: doc.item,
					attribute: doc.attribute,
                    lot: doc.lot
				}
			};
        })
	},
	onload_post_render: function(frm) {
        showOrHideColumns(frm, ['attribute_value'], 'process_cost_values', frm.doc.depends_on_attribute ? 0 : 1)
    },
	depends_on_attribute: function(frm) {
        showOrHideColumns(frm, ['attribute_value'], 'process_cost_values', frm.doc.depends_on_attribute ? 0 : 1)
        updateChildTableReqd(frm, ['attribute_value'], 'process_cost_values', frm.doc.depends_on_attribute ? 1 : 0)
        if (!frm.doc.depends_on_attribute) {
            removeAttributes(frm)
        }
    },
    refresh(frm){
        frm.get_field('process_cost_values').grid.cannot_add_rows = 1;
        frm.get_field('process_cost_values').grid.cannot_delete_rows = 1;
    },
    attribute(frm){
        if(frm.doc.attribute){
            frappe.call({
                method: "production_api.production_api.doctype.process_cost.process_cost.get_pc_attribute_values",
                args: {
                    lot: frm.doc.lot,
                    attribute: frm.doc.attribute,
                    process_name: frm.doc.process_name
                },
                callback: function(r){
                    frm.set_value('process_cost_values', [])
                    if(r.message && r.message.length){
                        r.message.forEach(row => {
                            let child = frm.add_child('process_cost_values');
                            child.attribute_value = row.attribute_value;
                            child.min_order_qty = row.min_order_qty;
                            child.price = row.price;
                        });
                    }
                    frm.refresh_field('process_cost_values');
                }
            })
        }
        else{
            frm.set_value('process_cost_values', []);
        }
    }
});

function removeAttributes(frm) {
    frm.set_value('attribute', undefined)
    $.each(frm.doc.process_cost_values || [], function(i, v) {
        frappe.model.set_value(v.doctype, v.name, "attribute_value", null)
    })
    frm.refresh_field("process_cost_values")
}

function updateChildTableReqd(frm, fields, table, reqd) {
    let grid = frm.get_field(table).grid;
    for (let row of grid.grid_rows) {
        if (row.open_form_button) {
            row.open_form_button.parent().remove();
            delete row.open_form_button;
        }
        
        for (let field in row.columns) {
            if (row.columns[field] !== undefined) {
                row.columns[field].remove();
            }
        }
        for (let fieldname of fields) {
			let df = row.docfields.find(field => field.fieldname === fieldname)
            df && (df.reqd = reqd)
            df && (df.read_only = 0)
        }
        
        delete row.columns;
        row.columns = [];
        row.render_row();
    }
    frappe.ui.form.editable_row && frappe.ui.form.editable_row.toggle_editable_row(false)
}

function showOrHideColumns(frm, fields, table, hidden) {
    if (frappe.ui.form.editable_row) {
        frappe.ui.form.editable_row.toggle_editable_row(false)
    }
    let grid = frm.get_field(table).grid;
    
    for (let field of fields) {
        grid.fields_map[field].hidden = hidden;
    }
    
    grid.visible_columns = undefined;
    grid.setup_visible_columns();
    
    grid.header_row.wrapper.remove();
    delete grid.header_row;
    grid.make_head();
    
    for (let row of grid.grid_rows) {
        if (row.open_form_button) {
            row.open_form_button.parent().remove();
            delete row.open_form_button;
        }
        
        for (let field in row.columns) {
            if (row.columns[field] !== undefined) {
                row.columns[field].remove();
            }
        }
        for (let fieldname of fields) {
			let df = row.docfields.find(field => field.fieldname === fieldname)
            df && (df.hidden = hidden)
        }
        
        delete row.columns;
        row.columns = [];
        row.render_row();
    }
    frappe.ui.form.editable_row && frappe.ui.form.editable_row.toggle_editable_row(false)
}