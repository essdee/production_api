frappe.pages["work-order-bulk-close"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Work Order Bulk Close"),
    single_column: true,
  });

  wrapper.work_order_bulk_close = new WorkOrderBulkClose(page);
};

frappe.pages["work-order-bulk-close"].on_page_show = function (wrapper) {
  const controller = wrapper.work_order_bulk_close;
  if (controller && controller.supplier_field.get_value()) {
    controller.load_work_orders();
  }
};

class WorkOrderBulkClose {
  constructor(page) {
    this.page = page;
    this.request_id = 0;
    this.work_orders = [];

    this.setup_filters();
    this.setup_body();
    this.render_empty_state(
      __("Select a supplier to view its open Work Orders.")
    );
  }

  setup_filters() {
    this.supplier_field = this.page.add_field({
      fieldname: "supplier",
      label: __("Supplier"),
      fieldtype: "Link",
      options: "Supplier",
      reqd: 1,
      change: () => this.load_work_orders(),
    });

    this.lot_field = this.page.add_field({
      fieldname: "lot",
      label: __("Lot"),
      fieldtype: "Link",
      options: "Lot",
      change: () => this.load_work_orders(),
    });

    this.item_field = this.page.add_field({
      fieldname: "item",
      label: __("Item"),
      fieldtype: "Link",
      options: "Item",
      change: () => this.load_work_orders(),
    });

    this.wo_from_date_field = this.page.add_field({
      fieldname: "wo_from_date",
      label: __("WO From Date"),
      fieldtype: "Date",
      change: () => this.load_work_orders(),
    });

    this.wo_to_date_field = this.page.add_field({
      fieldname: "wo_to_date",
      label: __("WO To Date"),
      fieldtype: "Date",
      change: () => this.load_work_orders(),
    });

    this.page.add_inner_button(__("Refresh"), () => this.load_work_orders());
  }

  setup_body() {
    this.body = $(
      `<div class="work-order-bulk-close-page">
        <style>
          .work-order-bulk-close-page .wo-bulk-card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: var(--border-radius-md);
            margin-top: 16px;
            overflow: hidden;
          }
          .work-order-bulk-close-page .wo-bulk-card-header {
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            min-height: 52px;
            padding: 12px 16px;
          }
          .work-order-bulk-close-page .wo-bulk-count {
            color: var(--text-muted);
            font-size: var(--text-sm);
          }
          .work-order-bulk-close-page .wo-bulk-table-wrap {
            overflow-x: auto;
          }
          .work-order-bulk-close-page table {
            margin-bottom: 0;
            min-width: 1050px;
          }
          .work-order-bulk-close-page th {
            background: var(--subtle-fg);
            position: sticky;
            top: 0;
            white-space: nowrap;
          }
          .work-order-bulk-close-page td {
            vertical-align: middle;
          }
          .work-order-bulk-close-page .wo-number {
            font-variant-numeric: tabular-nums;
            text-align: right;
            white-space: nowrap;
          }
          .work-order-bulk-close-page .wo-actions {
            display: flex;
            gap: 8px;
            white-space: nowrap;
          }
          .work-order-bulk-close-page .wo-bulk-empty {
            color: var(--text-muted);
            padding: 56px 20px;
            text-align: center;
          }
        </style>
        <div class="wo-bulk-card">
          <div class="wo-bulk-card-header">
            <strong>${__("Open Work Orders")}</strong>
            <span class="wo-bulk-count"></span>
          </div>
          <div class="wo-bulk-content"></div>
        </div>
      </div>`
    ).appendTo(this.page.main);

    this.content = this.body.find(".wo-bulk-content");
    this.count = this.body.find(".wo-bulk-count");
  }

  async load_work_orders() {
    const filters = this.get_filters();
    const filters_key = JSON.stringify(filters);
    const request_id = ++this.request_id;

    if (!filters.supplier) {
      this.work_orders = [];
      this.render_empty_state(
        __("Select a supplier to view its open Work Orders.")
      );
      return;
    }

    this.render_loading();

    try {
      const work_orders = await frappe.xcall(
        "production_api.production_api.page.work_order_bulk_close.work_order_bulk_close.get_open_work_orders",
        filters
      );

      if (
        request_id !== this.request_id ||
        filters_key !== JSON.stringify(this.get_filters())
      ) {
        return;
      }

      this.work_orders = work_orders || [];
      this.render_table();
    } catch {
      if (request_id === this.request_id) {
        this.render_empty_state(__("Unable to load Work Orders."));
      }
    }
  }

  get_filters() {
    return {
      supplier: this.supplier_field.get_value() || "",
      lot: this.lot_field.get_value() || "",
      item: this.item_field.get_value() || "",
      wo_from_date: this.wo_from_date_field.get_value() || "",
      wo_to_date: this.wo_to_date_field.get_value() || "",
    };
  }

  render_loading() {
    this.count.text(__("Loading..."));
    this.content.html(
      `<div class="wo-bulk-empty">
        <span class="spinner-border spinner-border-sm" role="status"></span>
        <div class="mt-2">${__("Fetching open Work Orders...")}</div>
      </div>`
    );
  }

  render_empty_state(message) {
    this.count.text("");
    this.content.html(
      `<div class="wo-bulk-empty">${this.escape_html(message)}</div>`
    );
  }

  render_table() {
    const count_label = __(
      this.work_orders.length === 1 ? "{0} Work Order" : "{0} Work Orders",
      [this.work_orders.length]
    );
    this.count.text(count_label);

    if (!this.work_orders.length) {
      this.render_empty_state(
        __("No open Work Orders found for this supplier.")
      );
      return;
    }

    const rows = this.work_orders
      .map(
        (work_order) => `<tr data-work-order="${this.escape_html(
          work_order.name
        )}">
          <td>
            <a href="/app/work-order/${encodeURIComponent(
              work_order.name
            )}" target="_blank">${this.escape_html(work_order.name)}</a>
          </td>
          <td>${this.format_date(work_order.wo_date)}</td>
          <td>${this.escape_html(work_order.item)}</td>
          <td>${this.escape_html(work_order.lot)}</td>
          <td>${this.escape_html(work_order.process_name)}</td>
          <td class="wo-number">${this.format_quantity(
            work_order.total_delivered
          )}</td>
          <td class="wo-number">${this.format_quantity(
            work_order.total_received
          )}</td>
          <td class="wo-number">${this.format_quantity(
            work_order.difference
          )}</td>
          <td>
            <div class="wo-actions">
              <button class="btn btn-xs btn-default wo-view" type="button">
                ${__("View")}
              </button>
              <button class="btn btn-xs btn-danger wo-close" type="button">
                ${__("Close")}
              </button>
            </div>
          </td>
        </tr>`
      )
      .join("");

    this.content.html(
      `<div class="wo-bulk-table-wrap">
        <table class="table table-bordered table-hover">
          <thead>
            <tr>
              <th>${__("Work Order ID")}</th>
              <th>${__("WO Date")}</th>
              <th>${__("Item")}</th>
              <th>${__("Lot")}</th>
              <th>${__("Process")}</th>
              <th class="wo-number">${__("Total Delivered")}</th>
              <th class="wo-number">${__("Total Received")}</th>
              <th class="wo-number">${__("Difference")}</th>
              <th>${__("Actions")}</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`
    );

    this.bind_row_actions();
  }

  bind_row_actions() {
    this.content.find("tbody tr").each((index, element) => {
      const work_order = this.work_orders[index];
      $(element)
        .find(".wo-view")
        .on("click", () => this.show_work_order_details(work_order));
      $(element)
        .find(".wo-close")
        .on("click", () => this.show_close_dialog(work_order));
    });
  }

  async show_work_order_details(work_order) {
    const dialog = new frappe.ui.Dialog({
      title: __("Pending Items - Close Work Order {0}", [work_order.name]),
      fields: [
        { fieldtype: "HTML", fieldname: "summary_html" },
        { fieldtype: "HTML", fieldname: "recut_html" },
        { fieldtype: "HTML", fieldname: "debit_list_html" },
      ],
      size: "extra-large",
    });

    dialog.show();
    $(dialog.fields_dict.summary_html.wrapper).html(
      `<div class="text-muted text-center" style="padding: 32px;">
        <span class="spinner-border spinner-border-sm" role="status"></span>
        <div class="mt-2">${__("Fetching Work Order details...")}</div>
      </div>`
    );

    try {
      const details = await frappe.xcall(
        "production_api.production_api.page.work_order_bulk_close.work_order_bulk_close.get_work_order_close_details",
        { work_order: work_order.name }
      );
      this.render_close_details(dialog, details || {});
    } catch {
      $(dialog.fields_dict.summary_html.wrapper).html(
        `<div class="text-danger text-center" style="padding: 32px;">
          ${__("Unable to load Work Order details.")}
        </div>`
      );
    }
  }

  render_close_details(dialog, details) {
    const item_detail = this.prepare_pending_summary(
      details.summary?.item_detail || []
    );
    const summary_wrapper = dialog.fields_dict.summary_html.wrapper;

    if (item_detail.length) {
      $(summary_wrapper).html(this.get_summary_html(item_detail));
    } else {
      $(summary_wrapper).html(
        `<p class="text-muted text-center" style="padding: 20px;">
          ${__("All items fully received")}
        </p>`
      );
    }

    $(dialog.fields_dict.recut_html.wrapper).html(
      this.get_recut_html(details.recut_details || [])
    );
    $(dialog.fields_dict.debit_list_html.wrapper).html(
      this.get_debit_html(details.debits || [])
    );
  }

  prepare_pending_summary(item_detail) {
    const groups = JSON.parse(JSON.stringify(item_detail || []));

    for (const group of groups) {
      for (const item of group.items || []) {
        const values = Object.values(item.values || {});
        item.total_qty = values.reduce(
          (total, value) => total + (value?.qty || 0),
          0
        );
        item.total_delivered = values.reduce(
          (total, value) => total + (value?.delivered || 0),
          0
        );
        item.total_received = values.reduce(
          (total, value) => total + (value?.received || 0),
          0
        );
      }

      group.items = (group.items || []).filter(
        (item) => (item.total_delivered || 0) - (item.total_received || 0) > 0
      );

      const total_details = {};
      let overall_planned = 0;
      let overall_delivered = 0;
      let overall_received = 0;

      for (const item of group.items) {
        for (const [attribute, value] of Object.entries(item.values || {})) {
          total_details[attribute] ||= {
            planned: 0,
            delivered: 0,
            received: 0,
          };
          total_details[attribute].planned += value?.qty || 0;
          total_details[attribute].delivered += value?.delivered || 0;
          total_details[attribute].received += value?.received || 0;
        }
        overall_planned += item.total_qty || 0;
        overall_delivered += item.total_delivered || 0;
        overall_received += item.total_received || 0;
      }

      group.total_details = total_details;
      group.overall_planned = overall_planned;
      group.overall_delivered = overall_delivered;
      group.overall_received = overall_received;
    }

    return groups.filter((group) => group.items.length);
  }

  get_summary_html(groups) {
    let html = `<h4>${__("Summary")}</h4>`;

    for (const group of groups) {
      const primary_values = group.primary_attribute_values?.length
        ? group.primary_attribute_values
        : ["default"];
      const item_label = group.pack_attr || __("Item");

      html += '<div class="table-responsive">';
      html += '<table class="table table-sm table-bordered">';
      html += `<thead><tr>
        <th>${__("S.No.")}</th>
        <th>${this.escape_html(item_label)}</th>`;
      if (group.is_set_item) {
        html += `<th>${this.escape_html(group.set_attr)}</th>`;
      }
      html += `<th>${__("Details")}</th>`;
      html += primary_values
        .map(
          (value) =>
            `<th>${
              value === "default" ? __("Quantity") : this.escape_html(value)
            }</th>`
        )
        .join("");
      html += `<th>${__("Total")}</th></tr></thead><tbody>`;

      group.items.forEach((item, index) => {
        const item_value =
          item.attributes?.[group.pack_attr] || item.name || "";
        const set_value = item.attributes?.[group.set_attr] || "";
        const detail_rows = [
          { label: __("Planned"), key: "qty", total: item.total_qty },
          {
            label: __("Delivered"),
            key: "delivered",
            total: item.total_delivered,
          },
          {
            label: __("Received"),
            key: "received",
            total: item.total_received,
          },
          {
            label: __("Pending"),
            key: "pending",
            total: (item.total_delivered || 0) - (item.total_received || 0),
          },
        ];

        detail_rows.forEach((detail, detail_index) => {
          html += "<tr>";
          if (detail_index === 0) {
            html += `<td rowspan="4">${index + 1}</td>`;
            html += `<td rowspan="4">${this.escape_html(item_value)}</td>`;
            if (group.is_set_item) {
              html += `<td rowspan="4">${this.escape_html(set_value)}</td>`;
            }
          }

          html += `<td>${this.emphasize_pending(
            detail.label,
            detail.key
          )}</td>`;
          for (const value of primary_values) {
            const value_details = item.values?.[value] || {};
            const quantity =
              detail.key === "pending"
                ? (value_details.delivered || 0) - (value_details.received || 0)
                : value_details[detail.key] || 0;
            html += `<td>${
              quantity > 0 ? this.format_quantity(quantity) : "--"
            }</td>`;
          }
          html += `<td>${this.emphasize_pending(
            this.format_quantity(detail.total),
            detail.key
          )}</td>`;
          html += "</tr>";
        });
      });

      const total_rows = [
        { label: __("Planned"), key: "planned", total: group.overall_planned },
        {
          label: __("Delivered"),
          key: "delivered",
          total: group.overall_delivered,
        },
        {
          label: __("Received"),
          key: "received",
          total: group.overall_received,
        },
        {
          label: __("Pending"),
          key: "pending",
          total: (group.overall_delivered || 0) - (group.overall_received || 0),
        },
      ];

      total_rows.forEach((total, total_index) => {
        html += "<tr>";
        if (total_index === 0) {
          html += `<td rowspan="4" colspan="${group.is_set_item ? 3 : 2}">
            <strong>${__("Total")}</strong>
          </td>`;
        }
        html += `<td>${this.emphasize_pending(total.label, total.key)}</td>`;

        for (const value of primary_values) {
          const value_details = group.total_details?.[value] || {};
          const quantity =
            total.key === "pending"
              ? (value_details.delivered || 0) - (value_details.received || 0)
              : value_details[total.key] || 0;
          html += `<td>${
            quantity > 0 ? this.format_quantity(quantity) : "--"
          }</td>`;
        }
        html += `<td>${this.emphasize_pending(
          this.format_quantity(total.total),
          total.key
        )}</td>`;
        html += "</tr>";
      });

      html += "</tbody></table></div>";
    }

    return html;
  }

  emphasize_pending(value, key) {
    return key === "pending" ? `<strong>${value}</strong>` : value;
  }

  get_recut_html(recut_details) {
    if (!recut_details.length) {
      return "";
    }

    let html = `<hr><h4>${__("WO Recut Details")}</h4>`;
    for (const recut of recut_details) {
      html += `<div style="margin-bottom: 15px;">
        <strong><a href="/app/wo-recut/${encodeURIComponent(
          recut.name
        )}" target="_blank">${this.escape_html(recut.name)}</a></strong>`;

      for (const group of recut.items || []) {
        const attributes = group.attributes || [];
        const primary_values = group.primary_attribute_values || [];
        html +=
          '<table class="table table-sm table-bordered" style="margin-top: 8px;">';
        html += `<thead><tr><th>${__("S.No.")}</th><th>${__("Item")}</th>`;
        html += attributes
          .map((attribute) => `<th>${this.escape_html(attribute)}</th>`)
          .join("");
        html += group.primary_attribute
          ? primary_values
              .map((value) => `<th>${this.escape_html(value)}</th>`)
              .join("")
          : `<th>${__("Quantity")}</th>`;
        html += `<th>${__("Total")}</th></tr></thead><tbody>`;

        (group.items || []).forEach((item, index) => {
          let total = 0;
          html += `<tr><td>${index + 1}</td><td>${this.escape_html(
            item.name
          )}</td>`;
          html += attributes
            .map(
              (attribute) =>
                `<td>${this.escape_html(item.attributes?.[attribute])}</td>`
            )
            .join("");

          if (group.primary_attribute) {
            for (const value of primary_values) {
              const quantity = item.values?.[value]?.qty || 0;
              total += quantity;
              html += `<td>${
                quantity > 0 ? this.format_quantity(quantity) : "--"
              }</td>`;
            }
          } else {
            const quantity = item.values?.default?.qty || 0;
            total = quantity;
            html += `<td>${
              quantity > 0 ? this.format_quantity(quantity) : "--"
            }</td>`;
          }

          html += `<td><strong>${this.format_quantity(
            total
          )}</strong></td></tr>`;
        });
        html += "</tbody></table>";
      }
      html += "</div>";
    }
    return html;
  }

  get_debit_html(debits) {
    if (!debits.length) {
      return "";
    }

    const rows = debits
      .map(
        (debit, index) => `<tr>
          <td>${index + 1}</td>
          <td><a href="/app/essdee-debit/${encodeURIComponent(
            debit.name
          )}" target="_blank">${this.escape_html(debit.name)}</a></td>
          <td>${this.escape_html(debit.debit_type)}</td>
          <td>${this.escape_html(debit.debit_no)}</td>
          <td>${format_currency(debit.debit_value || 0)}</td>
          <td class="text-center">
            <input type="checkbox" disabled ${
              debit.inspection ? "checked" : ""
            }>
          </td>
          <td>${this.escape_html(debit.status)}</td>
        </tr>`
      )
      .join("");

    return `<hr><h4>${__("Essdee Debits")}</h4>
      <table class="table table-sm table-bordered">
        <thead><tr>
          <th>${__("S.No.")}</th>
          <th>${__("Name")}</th>
          <th>${__("Debit Type")}</th>
          <th>${__("Debit No")}</th>
          <th>${__("Debit Value")}</th>
          <th>${__("Inspection")}</th>
          <th>${__("Status")}</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  show_close_dialog(work_order) {
    const dialog = new frappe.ui.Dialog({
      title: __("Close Work Order {0}", [work_order.name]),
      fields: [
        {
          fieldtype: "Select",
          fieldname: "close_reason",
          label: __("Close Reason"),
          options:
            "\nCutting Shortage\nPrinting Shortage\nSewing Shortage\nSewing Missing\nOthers",
          reqd: 1,
        },
        {
          fieldtype: "Data",
          fieldname: "close_other_reason",
          label: __("Other Reason"),
          depends_on: "eval: doc.close_reason == 'Others'",
          mandatory_depends_on: "eval: doc.close_reason == 'Others'",
        },
        {
          fieldtype: "Small Text",
          fieldname: "close_remarks",
          label: __("Close Remarks"),
        },
      ],
      primary_action_label: __("Close Work Order"),
      primary_action: (values) =>
        this.close_work_order(work_order, values, dialog),
    });

    dialog.show();
  }

  close_work_order(work_order, values, dialog) {
    const primary_button = dialog.get_primary_btn();
    primary_button.prop("disabled", true);

    frappe.call({
      method:
        "production_api.production_api.doctype.work_order.work_order.update_stock",
      args: {
        work_order: work_order.name,
        close_reason: values.close_reason,
        close_other_reason: values.close_other_reason || "",
        close_remarks: values.close_remarks || "",
      },
      freeze: true,
      freeze_message: __("Closing Work Order {0}...", [work_order.name]),
      callback: (response) => {
        if (response.exc) {
          primary_button.prop("disabled", false);
          return;
        }

        dialog.hide();
        const open_status = response.message?.open_status;
        frappe.show_alert({
          message:
            open_status === "Close Request"
              ? __("Close Request submitted for {0}.", [work_order.name])
              : __("Work Order {0} closed successfully.", [work_order.name]),
          indicator: open_status === "Close Request" ? "orange" : "green",
        });
        this.load_work_orders();
      },
      error: () => primary_button.prop("disabled", false),
    });
  }

  format_quantity(value) {
    return frappe.format(value || 0, {
      fieldtype: "Float",
      precision: 2,
    });
  }

  format_date(value) {
    return value ? frappe.datetime.str_to_user(value) : "";
  }

  escape_html(value) {
    return $("<div>")
      .text(value ?? "")
      .html();
  }
}
