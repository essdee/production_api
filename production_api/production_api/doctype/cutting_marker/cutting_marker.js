// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cutting Marker", {
	refresh(frm) {
        frm.set_df_property('cutting_marker_ratios','cannot_add_rows',true)
		frm.set_df_property('cutting_marker_ratios','cannot_delete_rows',true)
        $(frm.fields_dict['cutting_marker_ratios_html'].wrapper).html("")
        if(!frm.doc.__islocal){
            frm.marker_ratios = new frappe.production.ui.CuttingMarker($(frm.fields_dict['cutting_marker_ratios_html'].wrapper))
            if( frm.doc.__onload && frm.doc.__onload.marker_detail){
                frm.marker_ratios.load_data(frm.doc.__onload.marker_detail)
            }   
            else{
                frm.marker_ratios.load_data([])
            }
        }
	},
    validate(frm){
        if(frm.marker_ratios && !frm.doc.__islocal){
            let items = frm.marker_ratios.get_items()
            frm.doc['marker_details'] = items
        }
    }
});
