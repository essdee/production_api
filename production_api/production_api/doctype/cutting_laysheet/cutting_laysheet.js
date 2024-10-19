// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Cutting LaySheet", {
    refresh(frm) {
        frm.laysheet = new frappe.production.ui.LaySheetCloths(frm.fields_dict['cloths_html'].wrapper)
        if(frm.doc.__onload && frm.doc.__onload.item_details){
            frm.laysheet.load_data(frm.doc.__onload.item_details)
        }
        else{
            frm.laysheet.load_data([])
        }
        frm.set_df_property('cutting_laysheet_bundles','cannot_add_rows',true)
		frm.set_df_property('cutting_laysheet_bundles','cannot_delete_rows',true)
        if(frm.doc.cutting_laysheet_details.length > 0){
            frm.add_custom_button("Generate",()=> {
                frappe.call({
                    method:"production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_parts",
                    args: {
                        cutting_plan: frm.doc.cutting_plan,
                    },
                    callback:function(r){
                        let d =  new frappe.ui.Dialog({
                            title : "Enter Details",
                            fields: [
                                {
                                    fieldname:"parts_html",
                                    fieldtype:"HTML",
                                },
                                {
                                    fieldtype:"Int",
                                    fieldname:"maximum_no_of_plys",
                                    label:"Maximum No of Plys",
                                    reqd:true,
                                }
                            ],
                            primary_action:async function (values){
                                let items =await get_item_quantity(frm)
                                frappe.call({
                                    method:"production_api.production_api.doctype.cutting_laysheet.cutting_laysheet.get_cut_sheet_data",
                                    args: {
                                        doc_name : frm.doc.name,
                                        cutting_marker:frm.doc.cutting_marker,
                                        item_details:frm.doc.cutting_laysheet_details,
                                        items:items,
                                        max_plys:values.maximum_no_of_plys,
                                    },
                                })
                                d.hide()
                            }
                        })
                        d.show()
                        d.fields_dict.parts_html.$wrapper.html("")
                        d.fields_dict.parts_html.$wrapper.append(get_parts_html(r.message))
                    }
                })
            })
        }
	},
    validate(frm){
        let items = frm.laysheet.get_items()
        frm.doc['item_details'] = JSON.stringify(items)
    }
});

function get_parts_html(parts_list) {
    let htmlContent = `
        <table>
            <thead>
                <tr>
                    <th style="padding: 10px; border: 1px solid #ddd; background-color: #f4f4f4; font-size: 15px;">S.No</th>
                    <th style="padding: 10px; border: 1px solid #ddd; background-color: #f4f4f4; font-size: 15px;">Part</th>
                    <th style="padding: 10px; border: 1px solid #ddd; background-color: #f4f4f4; font-size: 15px;">Value</th>
                </tr>
            </thead>
            <tbody>
    `;
    for (let i = 0; i < parts_list.length; i++) {
        htmlContent += `
            <tr>
                <td style="padding: 10px; border: 1px solid #ddd; font-size: 12px;">${i + 1}</td>
                <td style="padding: 10px; border: 1px solid #ddd; font-size: 12px;">${parts_list[i]}</td>
                <td style="padding: 10px; border: 1px solid #ddd; font-size: 12px;">
                    <input type="number" class="quantity-input" value=${i + 1} style="width: 100%; padding: 5px; border: 1px solid #ccc;" />
                    <input type="hidden" class="part-name" value="${parts_list[i]}" />
                </td>
            </tr>
        `;
    }

    htmlContent += `</tbody></table>`;
    return htmlContent;
}


async function get_item_quantity(frm){
    let items = {}
    document.querySelectorAll('tr').forEach(row => {
        let partName = row.querySelector('.part-name')?.value;
        let quantity = row.querySelector('.quantity-input')?.value;
        
        if (partName && quantity) {
            items[partName] = quantity
        }
    });
    return items
}


