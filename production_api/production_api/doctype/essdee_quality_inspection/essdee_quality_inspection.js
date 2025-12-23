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
                let sizes = ""
                frm.doc.essdee_quality_inspection_sizes.forEach((size)=> {
                    if(size.selected == 1){
                        sizes+= size.size+","
                    }
                })
                sizes = sizes.slice(0, -1)
                let colours = ""
                frm.doc.essdee_quality_inspection_colours.forEach((colour)=> {
                    if(colour.selected == 1){
                        colours+= colour.colour+","
                    }
                })
                colours = colours.slice(0, -1)
                let caption = `
${frm.doc.inspection_type}
Supplier: ${frm.doc.supplier_name}
Style: ${frm.doc.item}
Lot: ${frm.doc.lot}
Size: ${sizes}
Colour: ${colours}
Description: ${frm.doc.description}
Order Qty: ${frm.doc.order_qty}
Offer Qty: ${frm.doc.offer_qty}
AQL Sample: ${frm.doc.sample_piece_count}
Allowed Major: ${frm.doc.major_defect_maximum_allowed}
Found Major: ${frm.doc.major_defect_found}
Allowed Minor: ${frm.doc.minor_defect_maximum_allowed}
Found Minor: ${frm.doc.minor_defect_found}
Result: ${frm.doc.result}
                `;
                try {
                    await navigator.clipboard.writeText(caption);
                    let file_url = frm.doc.upload_quality_approval_sheet;
                    let api_url = `/api/method/frappe.utils.file_manager.download_file?file_url=${encodeURIComponent(file_url)}`;
                    const response = await fetch(api_url, { credentials: "include" });
                    const blob = await response.blob();
                    const file = new File([blob], "inspection.jpg", { type: blob.type });
                    const shareData = { files: [file] };
                    await navigator.share(shareData);
                } 
                catch (err) {
                    console.error(err);
                    frappe.msgprint("Sharing failed.");
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
                    frm.set_value("supplier", r.message.supplier)
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
            frm.set_value("supplier", null)
            refresh_fields(frm)
        }
    }
});

function refresh_fields(frm){
    frm.refresh_field("item")
    frm.refresh_field("lot")
    frm.refresh_field("order_qty")
    frm.refresh_field("supplier")
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