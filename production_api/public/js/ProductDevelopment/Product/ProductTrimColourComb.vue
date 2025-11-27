<template>
	<div class="p-4 space-y-4">
        <div v-if="selected.length" class="mt-4">
			<h3 class="font-semibold mb-2">Selected {{view_page}} Images</h3>

			<div class="grid grid-cols-3 gap-3">
				<div 
                    v-for="(item, idx) in selected" 
                    :key="idx"
                    class="border rounded relative p-2"
                    style="padding-top: 10px;"
                >
                    <!-- FIXED X BUTTON -->
                    <button
                        class="absolute bg-red-500 text-white rounded-full flex items-center justify-center"
                        @click.stop="removeSelected(idx)"
                        style="
                            top: -6px !important;
                            right: -6px !important;
                            width: 22px;
                            height: 22px;
                            font-size: 12px;
                            box-shadow: 0 1px 4px rgba(0,0,0,0.3);
                            background-color: red;
                        "
                    >
                        ✕
                    </button>
                    <img 
                        :src="item.image_url"
                        class="rounded object-cover w-full"
                        style="height: 120px;"
                    />
                    <div 
                        class="grid mt-2 w-full"
                        style="display:grid; grid-template-columns: repeat(4, 1fr); gap:4px;"
                    >
                        <div
                            v-for="(clr, cidx) in colour_list"
                            :key="cidx"
                            class="flex flex-col items-center text-[9px] cursor-pointer"
                            style="width:100%;"
                        >
                            <input 
                                type="checkbox"
                                :value="clr.colour"
                                v-model="item.selected_colours"
                                class="w-3 h-3"
                                @click="make_dirty()"
                            />
                            <span class="truncate text-center w-full">{{ clr.colour }}</span>
                        </div>
                    </div>

                </div>
            </div>
        </div>
        <h3>Add {{view_page}} Images</h3>
        <input 
            v-model="query" 
            type="text" 
            class="border p-2 rounded w-full"
            placeholder="Search images..."
        />
        <div v-if="results.length" class="grid grid-cols-3 gap-3">
            <div 
                v-for="(item, idx) in results" 
                :key="idx"
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
import { ref, watch, onMounted } from "vue"

const query = ref("")
const results = ref([])
const selected = ref([])
const view_page = ref("")
const colour_list = ref([])

onMounted(() => {
    if (cur_frm.doc.is_set_item) {
        for (let i = 0; i < cur_frm.doc.product_set_colours.length; i++) {
            let top = cur_frm.doc.product_set_colours[i]
            let bottom = cur_frm.doc.product_set_colours[i]
            if (!colour_list.value.find(c => c.colour === top.top_colour)) {
                colour_list.value.push({
                    colour: top.top_colour,
                    colour_code: top.top_colour_code
                })
            }
            if (!colour_list.value.find(c => c.colour === bottom.bottom_colour)) {
                colour_list.value.push({
                    colour: bottom.bottom_colour,
                    colour_code: bottom.bottom_colour_code
                })
            }
        }
    } 
    else {
        for (let i = 0; i < cur_frm.doc.product_colours.length; i++) {
            let clr = cur_frm.doc.product_colours[i]
            if (!colour_list.value.find(c => c.colour === clr.product_colour)) {
                colour_list.value.push({
                    colour: clr.product_colour,
                    colour_code: clr.colour_code
                })
            }
        }
    }
})

watch(query, async (val) => {
	if (!val || val.length < 2) {
		results.value = []
		return
	}

	let res = await frappe.call({
		method: "production_api.product_development.doctype.product_image.product_image.get_image_list",
		args: { query: val },
	})

	results.value = res.message || []
})

function selectItem(item) {
	if (!selected.value.find(i => i.image_name === item.image_name)) {
		selected.value.push({
            ...item,
            selected_colours: [],
            colours_available: [...colour_list.value]   // TEMP until backend gives exact colours
        })
	}
    make_dirty()
}

function removeSelected(index) {
	selected.value.splice(index, 1)
    make_dirty()
}

function load_data(data, view) {
    view_page.value = view
    selected.value = data
}

function get_data() {
    return selected.value
}

function make_dirty(){
    if (!cur_frm.is_dirty()) {
        cur_frm.dirty()
    }
}

defineExpose({
    load_data,
    get_data
})
</script>
