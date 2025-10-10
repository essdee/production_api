<template>
    <div class="w-100 position-relative transition" style="margin-top:7px;" ref="multiSelect">
        <div class="p-2 rounded bg-blue text-dark border" style="height:100px; background-color: #f3f3f3;" @click="toggleDropdown">
            <div class="d-flex flex-wrap gap-1">
                <span v-if="!selectedValues.length">{{ placeholder }}</span>
                <span v-for="(value, index) in selectedValues" :key="index"
                    class="d-flex align-items-center bg-light text-dark rounded px-2 py-1 ms-2">
                    {{ value['option'] }}
                    <span v-if="docstatus == 0">
                        <button type="button" class="btn-close btn-close-white remove-btn"
                            aria-label="Close" @click.prevent.stop="removeOption(value)"> 
                            <svg version="1.1" id="Layer_1" xmlns="http://www.w3.org/2000/svg" 
                                xmlns:xlink="http://www.w3.org/1999/xlink" x="0px" y="0px" width="122.881px" height="122.88px" 
                                viewBox="0 0 122.881 122.88" enable-background="new 0 0 122.881 122.88" 
                                xml:space="preserve"><g><path fill-rule="evenodd" clip-rule="evenodd" 
                                d="M61.44,0c33.933,0,61.441,27.507,61.441,61.439 c0,33.933-27.508,61.44-61.441,61.44C27.508,122.88,0,95.372,0,61.439C0,27.507,27.508,0,61.44,0L61.44,0z M81.719,36.226 c1.363-1.363,3.572-1.363,4.936,0c1.363,1.363,1.363,3.573,0,4.936L66.375,61.439l20.279,20.278c1.363,1.363,1.363,3.573,0,4.937 c-1.363,1.362-3.572,1.362-4.936,0L61.44,66.376L41.162,86.654c-1.362,1.362-3.573,1.362-4.936,0c-1.363-1.363-1.363-3.573,0-4.937 l20.278-20.278L36.226,41.162c-1.363-1.363-1.363-3.573,0-4.936c1.363-1.363,3.573-1.363,4.936,0L61.44,56.504L81.719,36.226 L81.719,36.226z"/></g></svg>
                        </button>
                    </span>                           
                </span>
            </div>
        </div>
        <div v-if="isOpen" class="position-absolute mt-2 text-dark w-100 p-1 border rounded" style="z-index: 1050; background-color: #f3f3f3;" >
            {{get_options()}}
            <div v-if="show_options">
                <template v-for="(option) in options" v-if="options.length != 0">
                    <div :key="option" v-if="!selectedValues.includes(option)" @click.stop="selectOption(option)" 
                        class="rounded hover-bg-dark hover-text-white" style="cursor: pointer;">
                        {{ option['option'] }}
                    </div>
                </template>
                <div v-else>No Options Available</div>
            </div>
            <div v-else class="text-center">No Options Available</div>    
        </div>
    </div>
</template>

  
<script>
export default {
    name: 'MultiSelectFilter',
    props: {
        options: {
            type: Array,
            required: true,
        },
        placeholder : {
            type : String,
            required: false,
        },
        triggerEvent :{
            type : Function,
            required : true
        },
        setDefault : {
            type : Boolean,
            required : true
        },
        defaultList : {
            type : Array,
            required : true
        },
        item_key: {
            type: Number,
            required: true,
        },
        docstatus: {
            type: Number,
            required: false,
            default: 0
        },
    },
    data() {
        return {
            selectedValues: [],
            isOpen: false,
            show_options: false,
        };
    },
    mounted() {
        this.addClickEvent();
        if(this.setDefault && this.defaultList.length != 0){
            this.setDefaultValues();
        }
    },
    unmounted() {
        this.removeClickEvent();
    },
    methods: {
        addClickEvent(){
            document.addEventListener('click', this.handleClickOutside);
        },
        removeClickEvent(){
            document.removeEventListener('click', this.handleClickOutside);
        },
        toggleDropdown() {
            this.isOpen = !this.isOpen;
        },
        setDefaultValues() {
            this.options.forEach(element => {
                if(this.defaultList.includes(element['id'])){
                    this.selectedValues.push(element);
                }
            });
        },
        selectOption(option) {
            console.log("HELLO")
            if (this.selectedValues.includes(option)) {
                this.selectedValues = this.selectedValues.filter((val) => val !== option);
            } 
            else {
                this.selectedValues.push(option);
            }
            this.handleChange();
        },
        removeOption(option) {
            this.selectedValues = this.selectedValues.filter((val) => val !== option);
            this.handleChange();
        },
        handleClickOutside(event) {
            if (!this.$refs.multiSelect.contains(event.target)) {
                this.isOpen = false;
            }
        },
        handleChange(){
            console.log("HIHIHIHIHIHI")
            this.triggerEvent(this.selectedValues, this.item_key);
        },
        get_options() {
            if( this.options.length > 0) {
                let x = true
                for(let i = 0; i < this.options.length; i++) {
                    if (!this.selectedValues.includes(this.options[i])) {
                        console.log(this.options[i])
                        this.show_options = true
                        x = false
                        break
                    }
                }
                if (x) {
                    this.show_options = false
                }
            }
        }
    },
  };
</script>
<style scoped>
.dropdown {
    padding: 10px;
    border-radius: 8px;
    background-color: var(--control-bg);
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
    cursor: pointer;
    transition: all 0.3s ease;
}
.placeholder {
    color:var(--text-color);
}
.selected-options {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    overflow: hidden;
}
.tag {
    background-color: var(--control-bg);
    border: 1px solid var(--text-color);
    border-radius: 25px;
    padding: 7px 12px;
    display: flex;
    align-items: center;
    color: var(--text-color);
}
.remove-btn {
    background: none;
    border: none;
    margin-left: 6px;
    font-weight: bold;
    color: var(--text-color);
    cursor: pointer;
    border-radius: 50%;
    padding: 0;
    width: 16px;
    height: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
}
.remove-btn:hover {
    background-color: var(--control-bg);
}
.options-list {
    position: absolute;
    top: 100%;
    left: 0;
    width: 100%;
    background: var(--control-bg);
    border-radius: 8px;
    max-height: 200px;
    overflow-y: auto;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
    margin-top: 8px;
    z-index: 10;
    transition: max-height 0.3s ease;
}
.options-list div {
    padding: 5px 8px;
    cursor: pointer;
    color: var(--text-color);
}
.options-list div:hover {
    background-color: var(--text-color);
    color: var(--control-bg);
}
</style>