// Copyright (c) 2021, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item Item Attribute Mapping', {
	 refresh: function(frm) {
		frm.set_query('attribute_value','values', function(doc) {
			return {
				filters: {
					"attribute_name":frm.doc.attribute_name,	
				}
			};
		});
	 }
});

