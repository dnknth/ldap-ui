window.app = new Vue({
  el: "#app",
    data: {
      name: ''
    },
    computed: {
      showAlert() {
        return this.name.length > 4 ? true : false;
      }
    }
})
