// Copyright (c) 2024, Essdee and contributors
// For license information, please see license.txt

frappe.ui.form.on("Work Station", {
	setup: function(frm){
        frm.set_query("action",(doc)=> {
            return {
                filters :{
                    "capacity_planning" : true,
                }
            }
        })
	},
});
