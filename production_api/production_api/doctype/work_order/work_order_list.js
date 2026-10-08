frappe.listview_settings["Work Order"] = {
  onload: function (listview) {
    const desired_order = [
      "name",
      "status",
      "supplier",
      "lot",
      "item",
      "process_name",
    ];
    const filters_dict = listview.page.fields_dict;
    let reorder_fields = [];
    desired_order.forEach((key, idx) => {
      let x = filters_dict[key]["df"];
      reorder_fields.push(x);
    });
    let standard_filters_wrapper = listview.page.page_form.find(
      ".standard-filter-section",
    );
    if (standard_filters_wrapper.length) {
      standard_filters_wrapper.empty();
    }
    reorder_fields.map((df) => {
      cur_list.filter_area.list_view.page.add_field(
        df,
        standard_filters_wrapper,
      );
    });

    listview.page.add_action_item(__("Approve Close"), function () {
      const selected_items = listview.get_checked_items();
      if (!selected_items.length) {
        frappe.msgprint(__("Select at least one Work Order to approve."));
        return;
      }

      frappe.confirm(
        __("Approve close for {0} selected Work Orders?", [
          selected_items.length,
        ]),
        () => {
          frappe.call({
            method:
              "production_api.production_api.page.work_order_bulk_close.work_order_bulk_close.approve_close_requests",
            args: {
              work_orders: selected_items.map((item) => item.name),
            },
            freeze: true,
            freeze_message: __("Approving selected Work Orders..."),
            callback: (response) => {
              const results = response.message?.results || [];
              const failed = response.message?.failed || [];
              if (failed.length) {
                const closed_message =
                  results.length === 1
                    ? __("1 Work Order closed successfully.")
                    : __("{0} Work Orders closed successfully.", [
                        results.length,
                      ]);
                const failed_message =
                  failed.length === 1
                    ? __("1 Work Order failed:")
                    : __("{0} Work Orders failed:", [failed.length]);
                const failures = failed
                  .map(
                    (failure) =>
                      `<li><strong>${frappe.utils.escape_html(
                        failure.work_order,
                      )}</strong> — ${frappe.utils.escape_html(
                        failure.error,
                      )}</li>`,
                  )
                  .join("");
                frappe.msgprint({
                  title: __("Bulk Approve Close Result"),
                  indicator: results.length ? "orange" : "red",
                  message: `<p>${closed_message}</p><p>${failed_message}</p><ul>${failures}</ul>`,
                  wide: true,
                });
              } else {
                frappe.show_alert({
                  message: __("{0} Work Orders closed successfully.", [
                    results.length,
                  ]),
                  indicator: "green",
                });
              }
              listview.refresh();
            },
          });
        },
      );
    });
  },
  get_indicator: function (doc) {
    const status_colors = {
      Draft: "grey",
      Submitted: "blue",
      "Partially Delivered": "orange",
      "Fully Delivered": "green",
      "Partially Received": "yellow",
      "Fully Received": "green",
      "Partially Billed": "orange",
      "Fully Billed": "green",
      Closed: "black",
    };
    const color = status_colors[doc.status] || "blue";
    return [__(doc.status), color, "status,=," + doc.status];
  },
  refresh: function (frm) {
    let process = localStorage.getItem("process");
    let lot = localStorage.getItem("lot");
    localStorage.removeItem("process");
    localStorage.removeItem("lot");
    if (process && lot) {
      frm.filter_area.set([
        ["Work Order", "process_name", "=", process],
        ["Work Order", "docstatus", "=", 1],
        ["Work Order", "lot", "=", lot],
      ]);
      frm.refresh();
    }
  },
};
