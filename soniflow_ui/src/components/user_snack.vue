<template>
  <v-snackbar v-model="snackbar.show" :color="snackbar.color" timeout="2000" location="bottom right">
    <v-icon left class="mr-2">{{ snackIcon }}</v-icon>
    {{ snackbar.message }}
    <template v-slot:actions>
      <v-btn
        icon="mdi-close"
        variant="text"
        @click="snackbar.show = false"
      ></v-btn>
    </template>
  </v-snackbar>
</template>

<script setup>
import { ref, watch, computed } from 'vue';

const props = defineProps({
  message: String,
  color: {
    type: String,
    default: 'info',
  },
  show: Boolean,
});

const emit = defineEmits(['update:show']);

const snackbar = ref({
  show: props.show,
  message: props.message,
  color: props.color,
});

watch(() => props.show, (newVal) => {
  snackbar.value.show = newVal;
});

watch(() => props.message, (newVal) => {
  snackbar.value.message = newVal;
});

watch(() => props.color, (newVal) => {
  snackbar.value.color = newVal;
});

watch(() => snackbar.value.show, (newVal) => {
  emit('update:show', newVal);
});

const snackIcon = computed(() => {
  switch (snackbar.value.color) {
    case 'success':
      return 'mdi-check-circle';
    case 'error':
      return 'mdi-alert-circle';
    case 'warning':
      return 'mdi-alert';
    case 'info':
    default:
      return 'mdi-information';
  }
});
</script>
