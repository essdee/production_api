import { createApp } from 'vue'
import { FrappeUI, frappeRequest, setConfig } from 'frappe-ui'
import router from './router'
import App from './App.vue'
import './index.css'
import { socketio_port } from '../../../../sites/common_site_config.json'

import { registerControllers, registerGlobalComponents } from './globals'
// import { createToast } from './utils/toasts'

console.log(socketio_port)
let app = createApp(App)
app.use(router)
app.use(FrappeUI, {
    socketio: {
        port: socketio_port
    }
})
setConfig('resourceFetcher', (options) => {
	return frappeRequest({
		...options,
		onError(err) {
			if (err.error.messages && err.error.messages[0]) {
                console.log(err.error.messages[0])
				// createToast({
				// 	title: 'Error',
				// 	appearance: 'error',
				// 	message: err.error.messages[0],
				// })
			}
		},
	})
})
// app.provide(
// 	'$socket',
// 	initSocket({
// 		port: socketio_port,
// 	})
// )
registerGlobalComponents(app)
registerControllers(app)
app.mount('#app')
