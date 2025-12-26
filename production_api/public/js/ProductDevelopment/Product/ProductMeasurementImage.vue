<template>
    <div ref="root" class="p-3">
        <label class="form-label fw-bold">
            Measurement Image
        </label>
        <div class="image-box">
            <div v-if="doc.measurement_image" class="preview-box">
                <img 
                    :src="getImage(doc.measurement_image)" 
                    class="preview-img"
                >
            </div>
            <div v-if="docstatus == 1" style="padding-top: 10px; text-align: center;">
                <button 
                    class="btn btn-primary btn-sm mr-2"
                    @click="upload"
                >
                    <span v-if="!doc.measurement_image">Add Image</span>
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

function getImage(path) {
    if (!path) return "";
    if (path.startsWith("http")) return path;
    return window.location.origin + path;
}

function upload() {
    let old_file = doc.measurement_image; 
    let uploader = new frappe.ui.FileUploader({
        allow_multiple: false,
        folder: "Home",
        on_success: async (file) => {
            console.log({
                    file_url: old_file,
                    fieldname: "measurement_image",
                    docname: cur_frm.doc.name,
                    updated_url: file.file_url,
                    file_name: file.name
                })
            await frappe.call({
                method: "production_api.product_development.doctype.product.product.delete_and_update_file",
                args: {
                    file_url: old_file,
                    fieldname: "measurement_image",
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
        fieldname: "measurement_image",
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
                    fieldname: "measurement_image"
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
