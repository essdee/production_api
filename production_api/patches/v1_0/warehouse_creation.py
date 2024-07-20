import frappe

def execute():   
    parent = frappe.new_doc("Warehouse")
    parent.is_group = 1
    parent.warehouse_name = "All Warehouses"
    parent.save()

    supplier_warehouse = frappe.new_doc("Warehouse")
    supplier_warehouse.is_group = 1
    supplier_warehouse.warehouse_name = "Supplier Warehouses"
    supplier_warehouse.parent_warehouse = "All Warehouses"
    supplier_warehouse.save()

    transit_warehouse = frappe.new_doc("Warehouse")
    transit_warehouse.is_group = 1
    transit_warehouse.warehouse_name = "Transit Warehouses"
    transit_warehouse.parent_warehouse = 'All Warehouses'
    transit_warehouse.warehouse_type = 'Transit'
    transit_warehouse.save()

    transit = frappe.new_doc("Warehouse")
    transit.warehouse_name = "Transit"
    transit.parent_warehouse = 'Transit Warehouses'
    transit.warehouse_type = 'Transit'
    transit.save()
    
    stores = frappe.new_doc("Warehouse")
    stores.is_group = 1
    stores.warehouse_name = "Stores"
    stores.parent_warehouse = 'All Warehouses'
    stores.save()
    
    rejected_warehouse = frappe.new_doc("Warehouse")
    rejected_warehouse.is_group = 1
    rejected_warehouse.warehouse_name = "Rejected Warehouses"
    rejected_warehouse.parent_warehouse = 'All Warehouses'
    rejected_warehouse.warehouse_type = 'Rejected'
    rejected_warehouse.save()

    rework_warehouse = frappe.new_doc("Warehouse")
    rework_warehouse.is_group = 1
    rework_warehouse.warehouse_name = "Rework Warehouses"
    rework_warehouse.warehouse_type = 'Rework'
    rework_warehouse.parent_warehouse = 'All Warehouses'
    rework_warehouse.save()

    supp_list = frappe.get_list('Supplier',pluck='name')

    for supplier in supp_list:
        doc = frappe.get_doc("Supplier",supplier)
        if doc.is_company_location:
            acc_doc = frappe.new_doc("Warehouse")
            acc_doc.warehouse_name = doc.supplier_name
            acc_doc.parent_warehouse = "Stores"
            acc_doc.supplier = supplier
            acc_doc.save()

            rej_doc = frappe.new_doc("Warehouse")
            rej_doc.warehouse_name = "Rejected - " + doc.supplier_name 
            rej_doc.parent_warehouse = "Rejected Warehouses"
            rej_doc.warehouse_type = 'Rejected'
            rej_doc.supplier = supplier
            rej_doc.save()

            rework_doc = frappe.new_doc("Warehouse")
            rework_doc.warehouse_name = "Rework - " + doc.supplier_name
            rework_doc.parent_warehouse = "Rework Warehouses"
            rework_doc.warehouse_type = 'Rework'
            rework_doc.supplier = supplier
            rework_doc.save()
        else:
            new_doc = frappe.new_doc('Warehouse')
            new_doc.warehouse_name = doc.supplier_name
            new_doc.parent_warehouse = 'Supplier Warehouses'
            new_doc.supplier = supplier
            new_doc.save()

        doc.default_warehouse = doc.supplier_name
        doc.save()     
              