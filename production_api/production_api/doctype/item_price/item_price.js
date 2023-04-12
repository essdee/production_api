// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item Price', {
    setup: function(frm) {
        frm.set_query('attribute', function(doc) {
			if(!doc.item_name) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'item_name', doc.name))]));
			}
			return {
				query: 'production_api.production_api.doctype.item.item.get_item_attributes',
				filters: {
					item: doc.item_name,
				}
			};
		});
        frm.set_query('attribute_value', 'item_price_values', (doc) => {
            if(!doc.item_name) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'item_name', doc.name))]));
			}
            if(!doc.attribute) {
				frappe.throw(__("Please set {0}",
					[__(frappe.meta.get_label(doc.doctype, 'attribute', doc.name))]));
			}
			return {
				query: 'production_api.production_api.doctype.item.item.get_item_attribute_values',
				filters: {
					item: doc.item_name,
					attribute: doc.attribute,
				}
			};
        })
        frm.set_query('tax', function(doc) {
			return {
				filters: {
					enabled: 1,
				}
			};
		});
    },

	refresh: function(frm) {
        let now = new Date();
        frm.fields_dict.from_date.datepicker.update({
            minDate: now,
        });
        frm.fields_dict.to_date.datepicker.update({
            minDate: now,
        });
	},

    from_date:function(frm) {
        frm.fields_dict.to_date.datepicker.update({
            minDate: new Date(frm.doc.from_date)
        });
    },

    to_date:function(frm) {
        if (!frm.doc.to_date) {
            frm.fields_dict.from_date.datepicker.update({
                minDate: new Date(),
                maxDate: null,
            });
        } else {
            frm.fields_dict.from_date.datepicker.update({
                minDate: new Date(),
                maxDate: new Date(frm.doc.to_date),
            });
        }
        
    },

    onload_post_render: function(frm) {
        showOrHideColumns(frm, ['attribute_value'], 'item_price_values', frm.doc.depends_on_attribute ? 0 : 1)
    },

    depends_on_attribute: function(frm) {
        showOrHideColumns(frm, ['attribute_value'], 'item_price_values', frm.doc.depends_on_attribute ? 0 : 1)
        updateChildTableReqd(frm, ['attribute_value'], 'item_price_values', frm.doc.depends_on_attribute ? 1 : 0)
        if (!frm.doc.depends_on_attribute) {
            removeAttributes(frm)
        }
    },

    validate: function(frm) {
        if (!frm.doc.depends_on_attribute) {
            if (frm.doc.attribute) {
                frm.set_value('attribute', undefined)
            }
            
        }
    }
});

function removeAttributes(frm) {
    frm.set_value('attribute', undefined)
    $.each(frm.doc.item_price_values || [], function(i, v) {
        frappe.model.set_value(v.doctype, v.name, "attribute_value", null)
    })
    frm.refresh_field("item_price_values")
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
