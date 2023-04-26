<template>
  <div class="max-w-3xl py-12 mx-auto">
    <Button
      icon-left="code"
      @click="$resources.ping.fetch"
      :loading="$resources.ping.loading"
    >
      Click to send 'ping' request
    </Button>
    <div>
      {{ $resources.ping.data }}
    </div>
    <pre>{{ $resources.ping }}</pre>

    <Button @click="showDialog = true">Open Dialog</Button>
    <Button @click="showToast()">Show Toast</Button>
    <Dialog title="Title" v-model="showDialog"> Dialog content </Dialog>
  </div>
</template>

<script>
import { Dialog } from 'frappe-ui'

export default {
  name: 'Home',
  inject: ['$notify'],
  data() {
    return {
      showDialog: false,
    }
  },
  resources: {
    ping: {
      url: "ping",
      method: 'get',
    },
  },
  components: {
    Dialog,
  },
  methods: {
    showToast() {
      console.log(this)
      console.log(this.$notify)
      this.$notify({
        title: 'Title',
        message: 'Message',
        appearance: 'success',
      })
    },
  },
}
</script>
