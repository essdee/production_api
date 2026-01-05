<template>
	<div class="p-4 space-y-4">
        <div v-if="selected.length" class="mt-4">
			<h3 class="font-semibold mb-2">Selected {{view_page}} Images</h3>
            <div class="mt-2 w-full"
                style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px;"
            >
                <div v-for="(item, idx) in selected" :key="idx"
                    class="relative border rounded-lg overflow-hidden bg-white shadow-sm"
                    style="width: 100%;"
                >
                    <div style="width: 100%; text-align:center; display: flex;">
                        <div style="width: 90%;">
                            <img :src="item.image_url" class="w-full object-cover"
                                style="height: 140px; "
                            />
                        </div>
                        <div v-if="doctype != 'Product Release'">
                            <button @click.stop="removeSelected(idx)"
                                style="position: relative; top: 10px;"
                            >
                                ×
                            </button>
                        </div>
                    </div>    
                    <div class="grid mt-2 w-full"
                        style="display:grid; grid-template-columns: repeat(2, 1fr); gap:4px; padding-left: 20px;"
                    >
                        <div v-for="(clr, cidx) in colour_list" :key="cidx"
                            class="flex flex-col items-center text-[9px] cursor-pointer"
                            style="width:100%;"
                        >
                            <input 
                                type="checkbox"
                                :value="clr.colour"
                                v-model="item.selected_colours"
                                class="w-3 h-3"
                                style="margin-top: 5px;"
                                @click="make_dirty()"
                                :disabled="doctype == 'Product Release'"
                            />
                            <span class="truncate text-center w-full inline-block rounded-full px-2 py-1"
                                :style="{ 
                                    backgroundColor: colour_codes[clr.colour], 
                                    color: getTextColour(colour_codes[clr.colour]), 
                                    borderRadius: '10px',
                                }"
                            >
                                {{ clr.colour }}
                            </span>
                        </div>
                    </div>
                    <div class="p-1 text-sm text-center"
                        style="position: relative;"
                    >
                        {{ item.image_title || 'Untitled' }}
                    </div>
                </div>
            </div>
        </div>
        <div v-if="doctype != 'Product Release'">
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
	</div>
</template>

<script setup>
import { ref, watch, onMounted, reactive } from "vue"

const query = ref("")
const results = ref([])
const selected = ref([])
const view_page = ref("")
const colour_list = ref([])
let doctype = cur_frm.doc.doctype
const colour_codes = reactive({})

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
                colour_codes[top.top_colour] = top.top_colour_code
            }
            if (!colour_list.value.find(c => c.colour === bottom.bottom_colour)) {
                colour_list.value.push({
                    colour: bottom.bottom_colour,
                    colour_code: bottom.bottom_colour_code
                })
                colour_codes[bottom.bottom_colour] = bottom.bottom_colour_code
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
                colour_codes[clr.product_colour] = clr.product_colour_code
            }
        }
    }
})

function getTextColour(hex) {
    if (!hex) return '#000'
    hex = hex.replace('#', '')
    let r = parseInt(hex.substring(0, 2), 16)
    let g = parseInt(hex.substring(2, 4), 16)
    let b = parseInt(hex.substring(4, 6), 16)

    let yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000

    return yiq >= 128 ? '#000' : '#fff'
}


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
            colours_available: [...colour_list.value] 
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
