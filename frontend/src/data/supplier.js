import { createListResource } from 'frappe-ui'
import { computed } from 'vue'

export let suppliers = createListResource({
    doctype: "Supplier",
    fields: ["name", "supplier_name"],
    auto: true,
})
