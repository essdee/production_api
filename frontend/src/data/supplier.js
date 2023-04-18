import { createListResource } from 'frappe-ui'
import { computed } from 'vue'

export let suppliers = createListResource({
    doctype: "Supplier",
    fields: ["name", "supplier_name"],
    auto: true,
    onSuncess() {
        // console.log(this.data)
    },
})

export let suppliersOptions = computed(() => {
    return suppliers.data.map(supplier => {
        return {
            label: supplier.supplier_name,
            value: supplier.name
        }
    })
})