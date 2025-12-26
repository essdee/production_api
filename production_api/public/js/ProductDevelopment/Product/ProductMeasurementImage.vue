<template>
    <div ref="root" class="p-3">
        <label class="form-label fw-bold">
            Measurement Image
        </label>
        <div class="image-box">
            <div v-if="doc[image_field]" class="preview-box">
                <img 
                    :src="getImage(doc[image_field])" 
                    class="preview-img"
                >
            </div>
            <div v-if="docstatus != 1" style="padding-top: 10px; text-align: center;">
                <button 
                    class="btn btn-primary btn-sm mr-2"
                    @click="upload"
                >
                    <span v-if="!doc[image_field]">Add Image</span>
                    <span v-else>Update Image</span>
                </button>
                <button 
                    class="btn btn-secondary btn-sm"
                    @click="upload_pdf"
                >
                    Upload PDF
                </button>
            </div>
        </div>
    </div>
</template>


<script setup>
import { ref } from "vue";

const root = ref(null);
const doc = cur_frm.doc;    
const docstatus = cur_frm.doc.docstatus;
const image_field = cur_frm.doc.doctype == 'Product Measurement' ? 'measurement_image' : 'image';

function getImage(path) {
    if (!path) return "";
    if (path.startsWith("http")) return path;
    return window.location.origin + path;
}

function upload() {
    let old_file = doc[image_field]; 
    let uploader = new frappe.ui.FileUploader({
        allow_multiple: false,
        folder: "Home",
        on_success: async (file) => {
            if(!old_file){
                old_file = null
            }
            await frappe.call({
                method: "production_api.product_development.doctype.product.product.delete_and_update_file",
                args: {
                    file_url: old_file,
                    fieldname: image_field,
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

function upload_pdf() {
    new frappe.ui.FileUploader({
        doctype: cur_frm.doc.doctype,
        docname: cur_frm.doc.name,
        fieldname: image_field,
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
                    fieldname: image_field
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
</script>

<style scoped>
.image-box {
    border: 1px solid #e0e0e0;
    background: #fafafa;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 18px;
}

.image-box .btn {
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
}

.form-label {
    margin-bottom: 6px;
    margin-top: 10px;
}

.preview-box {
    width: 100%;
    height: 350px;
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
