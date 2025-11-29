frappe.ui.form.on("Essdee Quality Inspection", {
    setup(frm){
        frm.set_query('against_id',(doc)=> {
			return{
				filters: {
					'docstatus': 1,
				}
			}
		})
    },
    refresh(frm) {
        if (frm.colour_and_size && frm.colour_and_size.unmount) {
            frm.colour_and_size.unmount();
        }
        if(frm.is_new()){
            frappe.call({
                method: "production_api.production_api.doctype.essdee_quality_inspection.essdee_quality_inspection.get_default_aql_level",
                callback: function(r){
                    setTimeout(()=> {
                        frm.set_value("major_aql_level", r.message.major)
                        frm.set_value("minor_aql_level", r.message.minor)
                        frm.refresh_field("major_aql_level")
                        frm.refresh_field("minor_aql_level")
                    }, 500)
                }
            })
        }
        const wrapper = frm.fields_dict.size_and_colour_html.wrapper;
        wrapper.innerHTML = "";
        frm.colour_and_size = new frappe.production.ui.QualityInspection(wrapper);
        if(frm.doc.__onload && frm.doc.__onload.colour_size_data){
            frm.doc['colour_size_data'] = frm.doc.__onload.colour_size_data
            frm.colour_and_size.load_data(frm.doc.__onload.colour_size_data)
        }
        if(frm.doc.docstatus == 1){
            frm.set_df_property("result", "read_only", true)
            frm.add_custom_button("Share", async () => {
                if (!navigator.share || !navigator.canShare) {
                    frappe.msgprint("Sharing with image is not supported on this browser.");
                    return;
                }
                try {
                    let imageUrl = frm.doc.upload_quality_approval_sheet;
                    const response = await fetch(imageUrl);
                    const blob = await response.blob();
                    const file = new File([blob], "inspection.jpg", { type: blob.type });
                    const shareData = {
                        title: frm.doc.name,
                        text: "Sharing this inspection",
                        files: [file]
                    };
                    if (navigator.canShare(shareData)) {
                        await navigator.share(shareData);
                    } 
                    else {
                        frappe.msgprint("Cannot share image on this device.");
                    }
                } 
                catch (err) {
                    console.error("Sharing failed:", err);
                    frappe.msgprint("Image sharing failed.");
                }
            });
        }
        if(frm.doc.result == 'Hold' && frappe.perm.has_perm(frm.doc.doctype, 0, "cancel")){
            frm.add_custom_button("Update Status", ()=> {
                let d = new frappe.ui.Dialog({
                    title: "Select The Result",
                    fields: [
                        {
                            "label": "Result",
                            "fieldname": "result",
                            "fieldtype": "Select",
                            "options": ['Pass', "Fail"],
                            "reqd": 1
                        }
                    ],
                    primary_action(values){
                        frm.dirty()
                        frm.set_value("result", values.result)
                        frm.refresh_field("result")
                        frm.save_or_update()
                        d.hide()
                    }
                })
                d.show()
            })
        }
    },
    validate(frm) {
        if (frm.colour_and_size) {
            frm.doc.colour_and_size_data = frm.colour_and_size.get_data();
            frm.colour_and_size.unmount();
            frm.colour_and_size = null;
        }
    },
    offer_qty(frm){
        fetch_major_minor_allowed(frm)
    },
    checking_level(frm){
        fetch_major_minor_allowed(frm)
    },
    against_id(frm){
        if(frm.doc.against_id){
            frappe.call({
                method: "production_api.production_api.doctype.essdee_quality_inspection.essdee_quality_inspection.get_against_details",
                args: {
                    "against": frm.doc.against,
                    "against_id": frm.doc.against_id,
                }, 
                callback: function(r){
                    frm.set_value("item", r.message.item)
                    frm.set_value("lot", r.message.lot)
                    frm.set_value('order_qty', r.message.order_qty)
                    frm.set_value("unit_name", r.message.supplier)
                    refresh_fields(frm)
                    frm.colour_and_size.load_data({
                        "colours": r.message.colours,
                        "sizes": r.message.sizes,
                    })
                }
            })
        }
        else{
            frm.set_value("item", null)
            frm.set_value("lot", null)
            frm.set_value('order_qty', 0)
            frm.set_value("unit_name", null)
            refresh_fields(frm)
        }
    }
});

function refresh_fields(frm){
    frm.refresh_field("item")
    frm.refresh_field("lot")
    frm.refresh_field("order_qty")
    frm.refresh_field("unit_name")
}

function fetch_major_minor_allowed(frm){
    if(frm.doc.checking_level && frm.doc.offer_qty > 0){
        frappe.call({
            method: "production_api.production_api.doctype.essdee_quality_inspection.essdee_quality_inspection.get_max_minor_defect_allowed",
            args: {
                "level": frm.doc.checking_level,
                "offer_qty": frm.doc.offer_qty,
                "major_aql_level": frm.doc.major_aql_level,
                "minor_aql_level": frm.doc.minor_aql_level
            }, 
            callback: function(r){
                frm.set_value("sample_piece_count", r.message.sample)
                frm.set_value("major_defect_maximum_allowed", r.message.major_allowed)
                frm.set_value('minor_defect_maximum_allowed', r.message.minor_allowed)
                frm.refresh_field("sample_piece_count")
                frm.refresh_field("major_defect_maximum_allowed")
                frm.refresh_field("minor_defect_maximum_allowed")
            }
        })
    }
}