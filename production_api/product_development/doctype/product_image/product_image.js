// Copyright (c) 2025, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Product Image", {
    refresh(frm) {
        if (frm.is_new()) {
            $(frm.fields_dict['product_image_html'].wrapper).html('');
        }
        else {
            new frappe.production.product_development.ui.ProductMeasurementImage(frm.fields_dict['product_image_html'].wrapper);
        }
    },
});
