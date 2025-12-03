<template>
	<div class="p-4 space-y-4">
        <div v-if="selected.length" class="mt-4">
            <h3 class="font-semibold mb-2">
                Selected {{ view_page }} Images ({{ selected.length }})
            </h3>

            <div class="mt-2 w-full"
                style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;"
            >
                <div v-for="(item, idx) in selected" :key="idx"
                    class="relative border rounded-lg overflow-hidden bg-white shadow-sm"
                    style="width: 100%;"
                >
                    <div style="height: 85%; width: 100%; text-align:center; display: flex;">
                        <div style="width: 90%;">
                            <img :src="item.image_url" class="w-full object-cover"
                                style="height: 140px; "
                            />
                        </div>
                        <div>
                            <button @click.stop="removeSelected(idx)"
                                style="position: relative; z-index: 20; background-color: red; top: 10px;"
                            >
                                ×
                            </button>
                        </div>
                    </div>
                    <div class="p-1 text-sm text-center"
                        style="position: relative; z-index: 20;"
                    >
                        {{ item.image_title || 'Untitled' }}
                    </div>
                </div>
            </div>
        </div>

        <h3>Add {{view_page}} Images</h3>
		<input v-model="query" type="text" class="border p-2 rounded w-full"
			placeholder="Search images..."
		/>
		<div v-if="results.length" class="grid grid-cols-3 gap-3">
			<div v-for="(item, idx) in results" :key="idx"
				class="p-2 border rounded cursor-pointer hover:bg-gray-100"
				@click="selectItem(item)"
			>
            <img 
                :src="item.image_url"
                :style="{
                    minHeight: '100px',
                    height: '125px',
                    maxHeight: '150px',
                    maxWidth: '300px',
                }"
                class="object-cover rounded"
            />
				<div class="text-sm font-medium mt-1">{{ item.image_title }}</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { ref, watch } from "vue"

const query = ref("")
const results = ref([])
const selected = ref([])
const view_page = ref("")

watch(query, async (val) => {
	if (!val || val.length < 2) {
		results.value = []
		return
	}
	let res = await frappe.call({
		method: "production_api.product_development.doctype.product_image.product_image.get_image_list",
		args: { 
            query: val 
        },
	})

	results.value = res.message || []
})

function selectItem(item) {
	if (!selected.value.find(i => i.image_name === item.image_name)) {
		selected.value.push(item)
	}
    if(!cur_frm.is_dirty()){
        cur_frm.dirty()
    }
}

function removeSelected(index) {
	selected.value.splice(index, 1)
    if(!cur_frm.is_dirty()){
        cur_frm.dirty()
    }
}

function load_data(data, view){
    view_page.value = view
    selected.value = data
}

function get_data(){
    return selected.value
}

defineExpose({
    load_data,
    get_data
})

</script>
