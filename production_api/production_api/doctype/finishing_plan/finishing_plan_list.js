frappe.listview_settings["Finishing Plan"] = {
  add_fields: ["fp_status"],
  get_indicator: function (doc) {
    const status_colors = {
      "Planned": "grey",
      "Partially Received": "yellow",
      "Ready to Pack": "blue",
      "Partially Dispatched": "orange",
      "Dispatched": "green",
      "Fully Dispatched": "green",
      "OCR Requested": "red",
      "OCR Completed": "green",
      "P&L Submitted": "black",
    };
    const color = status_colors[doc.fp_status] || "grey";
    return [__(doc.fp_status || "Planned"), color, "fp_status,=," + (doc.fp_status || "Planned")];
  },
};
