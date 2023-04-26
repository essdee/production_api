import { createListResource } from 'frappe-ui'
import { computed } from 'vue'

export let supplierList = (args) => createListResource({
    fields: ["name", "supplier_name"],
    auto: true,
    ...args,
    doctype: "Supplier",
})
