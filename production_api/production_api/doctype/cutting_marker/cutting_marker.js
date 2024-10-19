// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cutting Marker", {
    setup:function(frm){
        frm.set_query("size","cutting_marker_parts", (doc)=> {
            let primary_list = []
            for(let i = 0 ; i < doc.cutting_marker_ratios.length; i++){
                primary_list.push(doc.cutting_marker_ratios[i]['size'])
            }
            return{
                filters: {
                    "attribute_value":["in",primary_list]
                }
            }
        })
        frm.set_query("part","cutting_marker_parts", (doc)=> {
            return{
                filters: {
                    "attribute_name": doc.cutting_attribute
                }
            }
        })
    },
	refresh(frm) {
        frm.set_df_property('cutting_marker_ratios','cannot_add_rows',true)
		frm.set_df_property('cutting_marker_ratios','cannot_delete_rows',true)
	},
    item(frm){
        if(frm.doc.item){
            frappe.call({
                method:"production_api.production_api.doctype.cutting_marker.cutting_marker.get_primary_attributes",
                args: {
                    item:frm.doc.item,
                },
                callback:((r)=> {
                    frm.set_value("cutting_marker_ratios",r.message)
                    frm.refresh_field("cutting_marker_ratios")
                })
            })
        }
    },
    calculate_parts(frm){
        frappe.call({
            method:"production_api.production_api.doctype.cutting_marker.cutting_marker.calculate_parts",
            args: {
                ratios :frm.doc.cutting_marker_ratios,
                cutting_plan: frm.doc.cutting_plan,
                doc_name: frm.doc.name,
            }
        })
    }
});
