frappe.listview_settings['Work Order'] = {
    onload: function (listview) {
        const desired_order = ['name', 'supplier', 'lot', 'item', 'process_name'];
        const filters_dict = listview.page.fields_dict;
        let reorder_fields = []
        desired_order.forEach((key, idx)=> {
            let x = filters_dict[key]['df']
            reorder_fields.push(x)
        })
        let standard_filters_wrapper = listview.page.page_form.find(
            ".standard-filter-section"
        );
        if (standard_filters_wrapper.length) {
            standard_filters_wrapper.empty(); 
        }
        reorder_fields.map((df) => {
            cur_list.filter_area.list_view.page.add_field(df, standard_filters_wrapper);
        });
    },
    refresh: function(frm){
        let process = localStorage.getItem("process")
        let lot = localStorage.getItem("lot")
        localStorage.removeItem("process")
        localStorage.removeItem("lot")
        if(process && lot){
            frm.filter_area.set([
                ["Work Order", "process_name", "=", process],
                ["Work Order", "docstatus", "=", 1],
                ["Work Order", "lot", "=", lot],
            ]);
            frm.refresh();
        }
    }
};
