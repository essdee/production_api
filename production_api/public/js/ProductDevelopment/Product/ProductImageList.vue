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
                        <div v-if="doctype != 'Product Release'">
                            <button @click.stop="removeSelected(idx)"
                                style="position: relative; top: 10px;"
                            >
                                ×
                            </button>
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
            <div style="display: flex;">
                <div>
                    <input v-model="query" type="text" class="border p-2 rounded w-full"
                        placeholder="Search images..."
                    />
                </div>
                <div style="padding-top: 5px;padding-left: 10px;">
                    <button @click="create_image()" class="btn btn-success">Create</button>
                </div>
            </div>
            
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
	</div>
</template>

<script setup>
import { ref, watch } from "vue"

const query = ref("")
const results = ref([])
const selected = ref([])
const view_page = ref("")
let doctype = cur_frm.doc.doctype

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

function create_image() {
    let d = new frappe.ui.Dialog({
        title: 'Create Product Image',
        fields: [
            {
                label: 'Image Title',
                fieldname: 'image_title',
                fieldtype: 'Data',
                reqd: 1
            },
            {
                label: 'Title Header',
                fieldname: 'title_header',
                fieldtype: 'Data',
                reqd: 1
            },
            {
                label: 'Upload Options',
                fieldname: 'upload_options',
                fieldtype: 'HTML',
            }
        ],
        primary_action_label: 'Save',
        async primary_action(values) {
            let exists = await frappe.db.exists('Product Image', values.image_title);
            if (exists) {
                frappe.msgprint(__('Product Image with title "{0}" already exists.', [values.image_title]));
                return;
            }
            
            let res = await frappe.call({
                method: 'frappe.client.insert',
                args: {
                    doc: {
                        doctype: 'Product Image',
                        image_title: values.image_title,
                        title_header: values.title_header
                    }
                }
            });
            
            if (res.message) {
                frappe.show_alert({
                    message: __('Product Image "{0}" created successfully', [values.image_title]),
                    indicator: 'green'
                });
                query.value = res.message.name;
                d.hide();
            }
        }
    });

    d.fields_dict.upload_options.$wrapper.html(`
        <div class="flex gap-2 mt-4" style="display: flex; gap: 8px; margin-top: 16px;">
            <button class="btn btn-primary btn-sm" id="btn_upload_image">Update Image</button>
            <button class="btn btn-secondary btn-sm" id="btn_upload_pdf">Upload PDF</button>
        </div>
    `);

    d.fields_dict.upload_options.$wrapper.find('#btn_upload_image').on('click', async () => {
        let values = d.get_values();
        if (!values) return;

        let exists = await frappe.db.exists('Product Image', values.image_title);
        if (exists) {
            frappe.msgprint(__('Product Image with title "{0}" already exists.', [values.image_title]));
            return;
        }

        let res = await frappe.call({
            method: 'frappe.client.insert',
            args: {
                doc: {
                    doctype: 'Product Image',
                    image_title: values.image_title,
                    title_header: values.title_header
                }
            }
        });

        if (res.message) {
            const doc = res.message;
            new frappe.ui.FileUploader({
                allow_multiple: false,
                folder: "Home",
                on_success: async (file) => {
                    await frappe.call({
                        method: "production_api.product_development.doctype.product.product.delete_and_update_file",
                        args: {
                            file_url: null,
                            fieldname: 'image',
                            doctype: 'Product Image',
                            docname: doc.name,
                            updated_url: file.file_url,
                            file_name: file.name
                        },
                        callback: function () {
                            frappe.show_alert({
                                message: __('Image uploaded successfully'),
                                indicator: 'green'
                            });
                            query.value = doc.name;
                            d.hide();
                        }
                    });
                }
            });
        }
    });
    d.fields_dict.upload_options.$wrapper.find('#btn_upload_pdf').on('click', async () => {
        let values = d.get_values();
        if (!values) return;

        let exists = await frappe.db.exists('Product Image', values.image_title);
        if (exists) {
            frappe.msgprint(__('Product Image with title "{0}" already exists.', [values.image_title]));
            return;
        }

        let res = await frappe.call({
            method: 'frappe.client.insert',
            args: {
                doc: {
                    doctype: 'Product Image',
                    image_title: values.image_title,
                    title_header: values.title_header
                }
            }
        });

        if (res.message) {
            const doc = res.message;
            new frappe.ui.FileUploader({
                doctype: 'Product Image',
                docname: doc.name,
                fieldname: 'image',
                folder: 'Home',
                restrictions: {
                    allowed_file_types: ['.pdf']
                },
                on_success: (file) => {
                    frappe.call({
                        method: "production_api.product_development.doctype.product.product.process_single_page_pdf",
                        args: {
                            file_url: file.file_url,
                            doctype: 'Product Image',
                            docname: doc.name,
                            fieldname: 'image'
                        },
                        freeze: true,
                        freeze_message: __("Processing PDF and extracting image..."),
                        callback: function (r) {
                            if (r.message) {
                                frappe.show_alert({
                                    message: __("PDF processed successfully"),
                                    indicator: 'green'
                                });
                                query.value = doc.name;
                                d.hide();
                            }
                        }
                    });
                }
            });
        }
    });

    d.show();
}

defineExpose({
    load_data,
    get_data
})

</script>
