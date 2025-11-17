frappe.listview_settings["Cutting Plan"] = {
    add_fields: ["cp_status", "no_of_colours", "no_of_colours_completed"],
	get_indicator: function (doc) {
		const status_color = {
			"Draft": "gray",
			"Planned": "blue",
			"Fabric Partially Received": "orange",
			"Ready to Cut": "purple",
            "Cutting In Progress": "yellow",
            "Partially Completed": "orange",
            "Completed": "green",
            "Cut Panel Dispatch Pending": "red"
		};
		let str = doc.cp_status
		if (!['Planned', 'Draft', 'Ready to Cut', 'Completed', 'Cutting In Progress'].includes(doc.cp_status)){
			str = str+"-"+doc.no_of_colours_completed+"/"+doc.no_of_colours
		}
		return [__(str), status_color[doc.cp_status], "cp_status,=," + doc.cp_status];
	},
	refresh(){
		$(".layout-side-section").css("display", "none")
	}
};
