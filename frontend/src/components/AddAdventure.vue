<template>
  <q-card>
    <q-form @submit="save">
      <q-card-section class="row items-center q-pb-none">
        <div class="text-h6">Add a new adventure</div>
        <q-space />
        <q-btn icon="close" flat round dense v-close-popup />
      </q-card-section>
      <q-card-section>
        <div class="q-gutter-lg">
          <q-input
            v-model="title"
            label="Session title"
            autofocus
            :rules="[(val) => !!val || 'Field is required']"
          />
          <q-input
            v-model="short_description"
            label="Short description"
            type="textarea"
            autogrow
            :rules="[(val) => !!val || 'Field is required']"
          />
          <q-input
            v-model="max_players"
            label="Max players"
            type="number"
            :min="1"
            :max="30"
            :rules="[(val) => !!val || 'Field is required']"
          />
          <DatePicker v-model="date" label="Date" />
          <q-select
            v-model.number="release_reminder_days"
            :options="releaseReminderOptions"
            emit-value
            map-options
            label="Release reminder"
          />
          <q-input
            v-model="tags"
            label="Tags"
            type="textarea"
            autogrow
          />
        </div>
      </q-card-section>
      <q-card-actions class="row justify-end">
        <q-btn
          label="Delete"
          color="negative"
          class="q-ma-md"
          v-if="editExisting"
          @click="confirmDeletion"
        />
        <q-space />
        <q-btn type="submit" label="Save" color="primary" class="q-ma-md" />
      </q-card-actions>
    </q-form>
  </q-card>
</template>

<script lang="ts">
import { defineComponent, inject } from 'vue';
import DatePicker from './DatePicker.vue';

export default defineComponent({
  name: 'AddAdventure',
  components: { DatePicker },
  emits: ['eventChange', 'canClose'],
  setup() {
    return {
      me: inject('me') as any,
    };
  },
  props: {
    editExisting: {
      type: Object,
      required: false,
    },
    eventTypeId: {
      type: Number,
      required: false,
    },
    defaultDate: {
      type: String,
      required: false,
    },
  },
  data() {
    return {
      title: this.editExisting?.title || '',
      short_description: this.editExisting?.short_description || '',
      max_players: this.editExisting?.max_players || 5,
      date: this.editExisting?.date || this.defaultDate || '',
      release_reminder_days: this.editExisting?.release_reminder_days ?? 2,
      tags: this.editExisting?.tags || null,
      releaseReminderOptions: [
        { label: '24 hours before', value: 1 },
        { label: '2 days before', value: 2 },
        { label: '3 days before', value: 3 },
        { label: '1 week before', value: 7 },
      ],
    };
  },
  computed: {
    filledIn() {
      return this.title != '' || this.short_description != '';
    },
  },
  methods: {
    async save() {
      const body = {
        title: this.title,
        short_description: this.short_description,
        max_players: this.max_players,
        date: this.date,
        release_reminder_days: this.release_reminder_days,
        event_type_id: this.eventTypeId,
        tags: this.tags,
      } as any;
      if (this.editExisting) {
        await this.$api.patch('/api/adventures/' + this.editExisting.id, body);
      } else {
        await this.$api.post('/api/adventures', body);
      }
      this.$q.notify({
        message: 'Your adventure was saved!',
        type: 'positive',
      });
      this.$emit('eventChange');
    },
    confirmDeletion() {
      this.$q
        .dialog({
          title: 'Delete',
          message: `Are you sure you want to delete "${this.editExisting!.title}" on the ${this.editExisting!.date}?` +
            (this.editExisting!.signups.length > 0 
              ? `\n${this.editExisting!.signups.length} player(s) have already signed up for this adventure.` 
              : ''),
          cancel: true,
        })
        .onOk(async () => {
          await this.$api.delete('/api/adventures/' + this.editExisting!.id);
          this.$q.notify({
            message: "And.. it's gone",
            type: 'positive',
          });
          this.$emit('eventChange');
        });
    },
  },
  watch: {
    filledIn(v) {
      this.$emit('canClose', !v);
    },
  },
});
</script>
