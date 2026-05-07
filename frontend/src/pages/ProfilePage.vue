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
      <q-item-label>Event and session updates</q-item-label>
      <q-item-label caption>Cancellation/removal updates for events and sessions</q-item-label>
    </q-item-section>
    <q-item-section side>
      <q-toggle v-model="notify_event_updates" color="primary" />
    </q-item-section>
  </q-item>

  <q-item tag="label" v-ripple>
    <q-item-section>
      <q-item-label>3-day signup confirmation</q-item-label>
      <q-item-label caption>Reminder 3 days before Immediate/Automatic events</q-item-label>
    </q-item-section>
    <q-item-section side>
      <q-toggle v-model="notify_signup_confirmation_3d" color="primary" />
    </q-item-section>
  </q-item>

  <q-item tag="label" v-ripple v-if="me?.privilege_level >= 1">
    <q-item-section>
      <q-item-label>Live signup updates</q-item-label>
      <q-item-label caption>Post-release signup updates for staff/admin event managers</q-item-label>
    </q-item-section>
    <q-item-section side>
      <q-toggle v-model="notify_live_signup_updates" color="primary" />
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
      notify_event_updates: me?.notify_event_updates ?? true,
      notify_signup_confirmation_3d: me?.notify_signup_confirmation_3d ?? true,
      notify_live_signup_updates: me?.notify_live_signup_updates ?? true,
    };
  },
  methods: {
    async save() {
      await this.$api.patch('/api/users/' + this.me.id, {
        display_name: this.display_name,
        notify_assignments: this.notify_assignments,
        notify_event_updates: this.notify_event_updates,
        notify_signup_confirmation_3d: this.notify_signup_confirmation_3d,
        notify_live_signup_updates: this.notify_live_signup_updates,
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
