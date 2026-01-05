<template>
    <div ref="root" class="p-3">
        <div v-if="is_set_item" style="width: 100%;display: flex; gap:2%;">
            <div style="width: 48%;">
                <label class="form-label fw-bold">
                    Top {{ text_value }} Image
                </label>
                <div class="image-box">
                    <div v-if="doc[fieldnames.top_image]" class="preview-box">
                        <img 
                            :src="doc[fieldnames.top_image]" 
                            class="preview-img"
                        >
                    </div>
                    <div v-if="doctype != 'Product Release'" style="padding-top: 10px; text-align: center;">
                        <button 
                            class="btn btn-primary btn-sm"
                            @click="upload(fieldnames.top_image)"
                        >
                            <span v-if="!doc[fieldnames.top_image]">Add Top Image</span>
                            <span v-else>Update Top Image</span>
                        </button>
                        <button 
                            class="btn btn-secondary btn-sm ml-2"
                            @click="upload_pdf(fieldnames.top_image)"
                        >
                            Upload PDF
                        </button>
                    </div>

                </div>
            </div>
            <div style="width: 48%;">
                <label class="form-label fw-bold">
                    Bottom {{ text_value }} Image
                </label>
                <div class="image-box">
                    <div v-if="doc[fieldnames.bottom_image]" class="preview-box">
                        <img 
                            :src="doc[fieldnames.bottom_image]" 
                            class="preview-img"
                        >
                    </div>
                    <div v-if="doctype != 'Product Release'" style="padding-top: 10px; text-align: center;">
                        <button 
                            class="btn btn-primary btn-sm"
                            @click="upload(fieldnames.bottom_image)"
                        >
                            <span v-if="!doc[fieldnames.bottom_image]">Add Bottom Image</span>
                            <span v-else>Update Bottom Image</span>
                        </button>
                        <button 
                            class="btn btn-secondary btn-sm ml-2"
                            @click="upload_pdf(fieldnames.bottom_image)"
                        >
                            Upload PDF
                        </button>
                    </div>
                </div>
            </div>
        </div>
        <div v-else class="image-box">
            <div v-if="doc[fieldnames.product_image]" class="preview-box">
                <img 
                    :src="doc[fieldnames.product_image]" 
                    class="preview-img"
                >
            </div>
            <div v-if="doctype != 'Product Release'" style="padding-top: 10px; text-align: center;">
                <button 
                    class="btn btn-primary btn-sm"
                    @click="upload(fieldnames.product_image)"
                >
                    <span v-if="!doc[fieldnames.product_image]">Add Image</span>
                    <span v-else>Update Image</span>
                </button>
                <button 
                    class="btn btn-secondary btn-sm ml-2"
                    @click="upload_pdf(fieldnames.product_image)"
                >
                    Upload PDF
                </button>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted } from "vue";

const root = ref(null);
const doc = cur_frm.doc;    
const is_set_item = doc.is_set_item;   
const fieldnames = ref({})
const text_value = ref(null)
let doctype = cur_frm.doc.doctype

function upload(fieldname) {
    let old_file = doc[fieldname]; 
    if(!old_file){
        old_file = null
    }
    let uploader = new frappe.ui.FileUploader({
        allow_multiple: false,
        folder: "Home",
        on_success: async (file) => {
            await frappe.call({
                method: "production_api.product_development.doctype.product.product.delete_and_update_file",
                args: {
                    file_url: old_file,
                    fieldname: fieldname,
                    doctype: cur_frm.doc.doctype,
                    docname: cur_frm.doc.name,
                    updated_url: file.file_url,
                    file_name: file.name
                },
                callback: function(){
                    cur_frm.reload_doc()
                }
            });
        }
    });
}

function upload_pdf(fieldname) {
    new frappe.ui.FileUploader({
        doctype: cur_frm.doc.doctype,
        docname: cur_frm.doc.name,
        fieldname: fieldname,
        folder: 'Home',
        restrictions: {
            allowed_file_types: ['.pdf']
        },
        on_success: (file) => {
            frappe.call({
                method: "production_api.product_development.doctype.product.product.process_single_page_pdf",
                args: {
                    file_url: file.file_url,
                    doctype: cur_frm.doc.doctype,
                    docname: cur_frm.doc.name,
                    fieldname: fieldname
                },
                freeze: true,
                freeze_message: __("Processing PDF and extracting image..."),
                callback: function(r) {
                    if (r.message) {
                        frappe.show_alert({
                            message: __("PDF processed successfully"),
                            indicator: 'green'
                        });
                        cur_frm.reload_doc();
                    }
                }
            });
        }
    });
}

function load_data(fields, text){
    fieldnames.value['top_image'] = fields['top_image']
    fieldnames.value['bottom_image'] = fields['bottom_image']
    fieldnames.value['product_image'] = fields['product_image']
    text_value.value = text
}

defineExpose({
    load_data
})
</script>

<style scoped>
.image-box {
    border: 1px solid #e0e0e0;
    background: #fafafa;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 18px;
}

/* Uploaded File Block */
.image-box strong {
    font-size: 13px;
    color: #444;
}

.image-box a {
    color: #0070f3;
    text-decoration: none;
}

.image-box a:hover {
    text-decoration: underline;
}

/* The box that contains "Uploaded File:" text */
.image-box .mb-2 {
    flex: 1;
    max-width: 80%;
}

/* Button styling (enhanced but Bootstrap-compatible) */
.image-box .btn {
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
}

/* Labels styling */
.form-label {
    margin-bottom: 6px;
    margin-top: 10px;
}

.preview-box {
    width: 100%;
    height: 230px;
    border: 1px solid #ddd;
    border-radius: 6px;
    overflow: hidden;
    background: white;
}

.preview-img {
    width: 100%;
    height: 100%;
    object-fit: contain;
}

</style>
