<template>
  <q-page class="row items-center justify-evenly">
    <q-form @submit="save" class="col-8">
      <q-card>
        <q-card-section class="q-gutter-lg">
          <div class="text-h6">User profile</div>
          <q-input v-model="display_name" label="Display name" />
          <q-separator class="q-my-md" />
<div class="text-subtitle1 text-weight-bold">Notification Preferences</div>
<q-list class="q-gutter-sm">
  <q-item tag="label" v-ripple>
    <q-item-section>
      <q-item-label>Assignments and waiting list updates</q-item-label>
      <q-item-label caption>Assignment release and waiting-list promotion updates</q-item-label>
    </q-item-section>
    <q-item-section side>
      <q-toggle v-model="notify_assignments" color="primary" />
    </q-item-section>
  </q-item>

  <q-item tag="label" v-ripple>
    <q-item-section>
      <q-item-label>Admin reminders</q-item-label>
      <q-item-label caption>Release reminders and new-event notifications (admins)</q-item-label>
    </q-item-section>
    <q-item-section side>
      <q-toggle v-model="notify_create_adventure_reminder" color="primary" />
    </q-item-section>
  </q-item>
</q-list>
        </q-card-section>
        <q-card-actions class="row justify-between">
          <q-btn label="Back" class="q-ma-md bg-blue-grey-7" to="/" />
          <q-btn type="submit" label="Save" color="primary" class="q-ma-md" />
        </q-card-actions>
      </q-card>
    </q-form>
  </q-page>
</template>

<script lang="ts">
import { defineComponent, inject } from 'vue';

export default defineComponent({
  name: 'ProfilePage',
  emits: ['changedUser', 'mustLogin'],
  setup() {
    return {
      me: inject('me') as any,
    };
  },
  data() {
    const me = this.me as any;
    if (!this.me) {
      this.$emit('mustLogin');
    }
    return {
      display_name: me?.display_name,
      notify_assignments: me?.notify_assignments ?? true,
      notify_create_adventure_reminder: me?.notify_create_adventure_reminder ?? false,
    };
  },
  methods: {
    async save() {
      await this.$api.patch('/api/users/' + this.me.id, {
        display_name: this.display_name,
        notify_assignments: this.notify_assignments,
        notify_create_adventure_reminder: this.notify_create_adventure_reminder,
      });
      this.$emit('changedUser');
      this.$q.notify({
        message: 'Your profile was saved!',
        type: 'positive',
      });
    },
  },
});
</script>
