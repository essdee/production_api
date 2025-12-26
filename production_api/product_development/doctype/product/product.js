// Copyright (c) 2023, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Product', {
	setup: function (frm) {
		frm.set_query("measurement", function () {
			return {
				filters: {
					"docstatus": 1
				}
			}
		})
		frm.set_query("top_measurement", function () {
			return {
				filters: {
					"docstatus": 1
				}
			}
		})
		frm.set_query("bottom_measurement", function () {
			return {
				filters: {
					"docstatus": 1
				}
			}
		})
	},
	refresh: function (frm) {
		if (frm.is_new()) {
			// $(frm.fields_dict['file_html'].wrapper).html("");
			$(frm.fields_dict['costing_html'].wrapper).html("");
			$(frm.fields_dict['product_silhouttes_html'].wrapper).html("");
			$(frm.fields_dict['product_placement_html'].wrapper).html("");
			$(frm.fields_dict['product_trims_html'].wrapper).html("");
			$(frm.fields_dict['trim_colour_combination_html'].wrapper).html("");
			$(frm.fields_dict['measurement_images_html'].wrapper).html("");
			$(frm.fields_dict['product_measurement_html'].wrapper).html("");
		}
		else {
			// $(frm.fields_dict['file_html'].wrapper).html("");
			$(frm.fields_dict['costing_html'].wrapper).html("");
			// let fileEditor = new frappe.production.product_development.ui.ProductFileVersions(frm.fields_dict["file_html"].wrapper);
			let costingList = new frappe.production.product_development.ui.ProductCostingList(frm.fields_dict["costing_html"].wrapper);
		}
		frm.silhoutte = new frappe.production.product_development.ui.ProductSilhoutte(frm.fields_dict['product_silhouttes_html'].wrapper)
		frm.silhoutte.load_data({
			"top_image": "top_image",
			"bottom_image": "bottom_image",
			"product_image": "product_image",
		}, null)
		new frappe.production.product_development.ui.ProductGraphics(frm.fields_dict['product_design_html'].wrapper)
		frm.placement = new frappe.production.product_development.ui.ProductImageList(frm.fields_dict['product_placement_html'].wrapper);
		if (frm.doc.__onload && frm.doc.__onload.placement_images) {
			frm.doc['placement_images'] = frm.doc.__onload.placement_images
			frm.placement.load_data(frm.doc.__onload.placement_images, "Placement")
		}
		else {
			frm.placement.load_data([], "Placement")
		}
		frm.product_trims = new frappe.production.product_development.ui.ProductImageList(frm.fields_dict['product_trims_html'].wrapper)
		if (frm.doc.__onload && frm.doc.__onload.trims_images) {
			frm.doc['trims_images'] = frm.doc.__onload.trims_images
			frm.product_trims.load_data(frm.doc.__onload.trims_images, "Trims")
		}
		else {
			frm.product_trims.load_data([], "Trims")
		}
		frm.trim_comb = new frappe.production.product_development.ui.ProductTrimColourComb(frm.fields_dict['trim_colour_combination_html'].wrapper)
		if (frm.doc.__onload && frm.doc.__onload.trims_combination) {
			frm.doc['trims_combination'] = frm.doc.__onload.trims_combination
			frm.trim_comb.load_data(frm.doc.__onload.trims_combination, "Combination")
		}
		else {
			frm.trim_comb.load_data([], "Combination")
		}
		frm.box_detail = new frappe.production.product_development.ui.ProductGraphics(frm.fields_dict['box_detail_html'].wrapper)
		frm.box_detail.load_data("Box Data")
		frm.measurement = new frappe.production.product_development.ui.ProductMeasurement(frm.fields_dict['product_measurement_html'].wrapper)
		if (frm.doc.__onload && frm.doc.__onload.measurement_details) {
			frm.doc['measurement_details'] = frm.doc.__onload.measurement_details
			frm.measurement.load_data(frm.doc.__onload.measurement_details)
		}
		frm.accessories = new frappe.production.product_development.ui.ProductImageList(frm.fields_dict['product_accessories_html'].wrapper);
		if (frm.doc.__onload && frm.doc.__onload.accessory_images) {
			frm.doc['accessory_images'] = frm.doc.__onload.accessory_images
			frm.accessories.load_data(frm.doc.__onload.accessory_images, "Accessory")
		}
		else {
			frm.accessories.load_data([], "Accessory")
		}
		frm.add_custom_button("Release Tech Pack", () => {
			let d = new frappe.ui.Dialog({
				title: "Are you sure want to release Tech Pack",
				primary_action_label: "Yes",
				secondary_action_label: "No",
				primary_action() {
					frappe.call({
						method: "production_api.product_development.doctype.product.product.release_tech_pack",
						args: {
							"doc_name": frm.doc.name,
						},
						freeze: true,
						freeze_message: "Releasing Tech Pack",
						callback: function (r) {
							if (r.message) {
								frappe.msgprint("Tech Pack Released")
							}
						}
					})
				},
				secondary_action() {
					d.hide()
				}
			})
			d.show()
		})

		frm.add_custom_button("Print Tech Pack", () => {
			let w = window.open(
				frappe.urllib.get_full_url(
					"/printview?" + "doctype=" + encodeURIComponent(frm.doc.doctype) + "&name=" +
					encodeURIComponent(frm.doc.name) + "&trigger_print=1" + "&format=" +
					encodeURIComponent('Product Tech Pack') + "&no_letterhead=1"
				)
			);
			if (!w) {
				frappe.msgprint(__("Please enable pop-ups"));
				return;
			}
		})
	},

	size_range: function (frm) {
		if (frm.doc.size_range) {
			frm.trigger("get_sizes");
		} else {
			frm.set_value("sizes", []);
		}
	},

	get_sizes: function (frm) {
		frappe.db.get_doc("FG Item Size Range", frm.doc.size_range).then(size_range => {
			frm.set_value("sizes", []);
			size_range.sizes.forEach(size => {
				let row = frm.add_child("sizes");
				row.attribute_value = size.attribute_value;
			});
			frm.refresh_field("sizes");
		});
	},

	validate(frm) {
		if (frm.placement) {
			frm.doc['placement_images'] = frm.placement.get_data()
		}
		if (frm.product_trims) {
			frm.doc['product_trims_images'] = frm.product_trims.get_data()
		}
		if (frm.trim_comb) {
			frm.doc['trim_comb'] = frm.trim_comb.get_data()
		}
		if (frm.measurement) {
			frm.doc['measurement_details'] = frm.measurement.get_data()
		}
		if (frm.accessories) {
			frm.doc['accessory_images'] = frm.accessories.get_data()
		}
	}
});
