// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Product Release', {
	refresh: function(frm) {
		if (frm.is_new()) {
			$(frm.fields_dict['product_silhouttes_html'].wrapper).html("");
			$(frm.fields_dict['product_placement_html'].wrapper).html("");
			$(frm.fields_dict['product_trims_html'].wrapper).html("");
			$(frm.fields_dict['trim_colour_combination_html'].wrapper).html("");
			$(frm.fields_dict['measurement_images_html'].wrapper).html("");
			$(frm.fields_dict['product_measurement_html'].wrapper).html("");
		} 
		frm.silhoutte = new frappe.production.product_development.ui.ProductSilhoutte(frm.fields_dict['product_silhouttes_html'].wrapper)
		frm.silhoutte.load_data({
			"top_image": "top_image",
			"bottom_image": "bottom_image",
			"product_image": "product_image",
		}, null)
		new frappe.production.product_development.ui.ProductGraphics(frm.fields_dict['product_design_html'].wrapper)
		frm.placement = new frappe.production.product_development.ui.ProductImageList(frm.fields_dict['product_placement_html'].wrapper);
		if(frm.doc.__onload && frm.doc.__onload.placement_images){
			frm.doc['placement_images'] = frm.doc.__onload.placement_images
			frm.placement.load_data(frm.doc.__onload.placement_images, "Placement")
		}
		else{
			frm.placement.load_data([], "Placement")
		}
		frm.product_trims = new frappe.production.product_development.ui.ProductImageList(frm.fields_dict['product_trims_html'].wrapper)
		if(frm.doc.__onload && frm.doc.__onload.trims_images){
			frm.doc['trims_images'] = frm.doc.__onload.trims_images
			frm.product_trims.load_data(frm.doc.__onload.trims_images, "Trims")
		}
		else{
			frm.product_trims.load_data([], "Trims")
		}
		frm.trim_comb = new frappe.production.product_development.ui.ProductTrimColourComb(frm.fields_dict['trim_colour_combination_html'].wrapper)
		if(frm.doc.__onload && frm.doc.__onload.trims_combination){
			frm.doc['trims_combination'] = frm.doc.__onload.trims_combination
			frm.trim_comb.load_data(frm.doc.__onload.trims_combination, "Combination")
		}
		else{
			frm.trim_comb.load_data([], "Combination")
		}
		frm.box_detail = new frappe.production.product_development.ui.ProductGraphics(frm.fields_dict['box_detail_html'].wrapper)
		frm.box_detail.load_data("Box Data")
		frm.measurement = new frappe.production.product_development.ui.ProductMeasurement(frm.fields_dict['product_measurement_html'].wrapper)
		if(frm.doc.__onload && frm.doc.__onload.measurement_details){
			frm.doc['measurement_details'] = frm.doc.__onload.measurement_details
			frm.measurement.load_data(frm.doc.__onload.measurement_details)
		}
		frm.accessories = new frappe.production.product_development.ui.ProductImageList(frm.fields_dict['product_accessories_html'].wrapper);
		if(frm.doc.__onload && frm.doc.__onload.accessory_images){
			frm.doc['accessory_images'] = frm.doc.__onload.accessory_images
			frm.accessories.load_data(frm.doc.__onload.accessory_images, "Accessory")
		}
		else{
			frm.accessories.load_data([], "Accessory")
		}
		frm.add_custom_button("Print Tech Pack", ()=> {
			let w = window.open(
				frappe.urllib.get_full_url(
					"/printview?" + "doctype=" + encodeURIComponent(frm.doc.doctype) + "&name=" +
						encodeURIComponent(frm.doc.name) + "&trigger_print=1" + "&format=" + 
						encodeURIComponent('Tech Pack') + "&no_letterhead=1"
				)
			);
			if (!w) {
				frappe.msgprint(__("Please enable pop-ups"));
				return;
			}
		})
	},
});
