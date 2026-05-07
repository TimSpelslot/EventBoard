<template>
  <q-layout view="lHh Lpr lFf">
    <q-header elevated>
      <q-toolbar class="row justify-between">
        <div class="q-gutter-x-md">
          <q-btn label="Events" icon="home" to="/" />
          <q-btn label="Sessions" icon="event_available" to="/sessions" />
          <q-btn label="FAQ" icon="help" to="/faq" />
        </div>
        <q-avatar icon="img:spelslot-logo.svg" size="50px"></q-avatar>
        <div class="q-gutter-x-sm">
          <q-btn icon="notifications" color="primary" @click="setupNotifications" />
          <q-toggle class="q-sm-md" label="Noob" v-if="me?.privilege_level > 0 || droppedPrivileges" color="secondary" :modelValue="droppedPrivileges" @update:modelValue="togglePrivileges" />
          <q-spinner size="lg" v-if="adminActionsActive > 0" />
          <q-btn
            v-if="me"
            :icon="me.profile_pic ? 'img:' + me.profile_pic : 'settings'"
            :label="me.display_name"
          >
            <q-menu>
              <q-list style="min-width: 100px">
                <q-item to="/profile">
                  <q-item-section>Edit profile</q-item-section>
                </q-item>
                <q-item v-if="me" to="/admin/events">
                  <q-item-section>Event operations</q-item-section>
                </q-item>
                <q-item clickable v-close-popup @click="logout">
                  <q-item-section>Log out</q-item-section>
                </q-item>
                <q-separator v-if="me.privilege_level >= 2" />
                <template v-if="me.privilege_level >= 2">
                  <q-item to="/admin/users">
                    <q-item-section>Approve users</q-item-section>
                  </q-item>
                  <q-item
                    clickable
                    v-close-popup
                    @click="adminAction('assign')"
                  >
                    <q-item-section>Make assignments</q-item-section>
                  </q-item>
                  <q-item
                    clickable
                    v-close-popup
                    @click="adminAction('reassign')"
                  >
                    <q-item-section>Reassigne players form the waitinglist</q-item-section>
                  </q-item>
                  <q-item
                    clickable
                    v-close-popup
                    @click="adminAction('release')"
                  >
                    <q-item-section>Release assignments</q-item-section>
                  </q-item>
                  <q-item
                    clickable
                    v-close-popup
                    @click="adminAction('reset')"
                  >
                    <q-item-section>Reset released assignments</q-item-section>
                  </q-item>
                  <q-item clickable v-close-popup @click="signups">
                    <q-item-section>See current signups</q-item-section>
                  </q-item>
                </template>
              </q-list>
            </q-menu>
          </q-btn>
          <q-btn v-else label="Login" @click="login" icon="login" />
          <q-btn
            color="primary"
            @click="toggleDarkMode"
            :icon="darkModeIcon"
          />
        </div>
      </q-toolbar>
    </q-header>

    <q-page-container>
      <q-page v-if="errors.length > 0" class="q-px-lg q-pt-md">
        <div class="column flex flex-center q-my-xl">
          <q-spinner size="xl" />
          <div class="text-h6 q-mt-md text-center">
            Oh no, our servers rolled a natural one.
          </div>
          <div class="text-subtitle2 text-center q-mt-sm">
            Please wait or inform admins.
          </div>
        </div>
        <q-banner v-for="e in errors" :key="e" class="bg-negative" rounded>{{
          e
        }}</q-banner>
      </q-page>
      <q-page v-else-if="loading" class="q-px-lg q-pt-md">
        <div class="column flex flex-center q-my-xl">
          <q-spinner size="xl" />
          <div class="text-h6 q-mt-md text-center">Loading...</div>
        </div>
      </q-page>
      <router-view
        v-else
        @setErrors="(es) => (errors = es)"
        @changedUser="fetchMe"
        @mustLogin="login"
        @startAdminAction="adminActionsActive++"
        @finishAdminAction="adminActionsActive--"
      />
      <a href="https://github.com/SpelSlot-IT/AdventureBoard" class="fixed-bottom-right q-mr-sm">
        <q-icon name="img:https://github.com/favicon.ico" size="lg" class="bg-grey-5" />
      </a>
    </q-page-container>
  </q-layout>
</template>

<script lang="ts">
import { defineComponent, computed } from 'vue';
import { isAxiosError } from 'axios';
import { getFCMToken } from '../lib/fcm';

export default defineComponent({
  name: 'MainLayout',

  data() {
    return {
      loading: true,
      errors: [] as string[],
      adminActionsActive: 0,
      forceRefresh: 1,
      droppedPrivileges: false,
      me: null as null | {
        id: number;
        display_name: string;
        privilege_level: number;
        profile_pic: string;
      },
    };
  },

  methods: {
    toggleDarkMode() {
      const darkModeEnabled = !this.$q.dark.isActive;
      localStorage.setItem('darkMode', String(+darkModeEnabled));
      this.$q.dark.set(darkModeEnabled);
    },
    async fetchMe() {
      this.me = (await this.$api.get('/api/users/me')).data;
      if(this.droppedPrivileges) {
        this.me!.privilege_level = 0;
      }
    },
    async logout() {
      const currentUrl = window.location.href;
      window.location.href = `/api/logout?next=${encodeURIComponent(
        currentUrl
      )}`;
    },
    async login() {
      const currentUrl = window.location.href;
      window.location.href = `/api/login?next=${encodeURIComponent(
        currentUrl
      )}`;
    },
    async signups() {
      window.location.href = '/#/signups';
    },

    async adminAction(action: string) {
      this.adminActionsActive++;
      try {
        await this.$api.put('/api/player-assignments', { action: action });
        this.forceRefresh++;
        this.$q.notify({
          message: `${
            action.charAt(0).toUpperCase() + action.slice(1)
          } triggered.`,
          type: 'positive',
        });
      } finally {
        this.adminActionsActive--;
      }
    },
    async optionallyFetchUser() {
      try {
        await this.fetchMe();
      } catch (e) {
        if (isAxiosError(e) && e.response?.status == 401) {
          // Not logged in. That's fine.
        } else {
          throw e;
        }
      }
    },
    togglePrivileges(v: boolean) {
      this.droppedPrivileges = v;
      if(v) {
        this.me!.privilege_level = 0;
      } else {
        this.fetchMe();
      }
    },
    async setupNotifications() {
      if (!this.me) {
        this.$q.notify({
          color: 'negative',
          message: 'You need to be logged in to enable notifications.',
          icon: 'error'
        });
        return;
      }
      try {
        const permission = await Notification.requestPermission();
        if (permission !== 'granted') {
          this.$q.notify({
            color: 'negative',
            message: 'Permission denied for notifications.',
            icon: 'notifications_off'
          });
          return;
        }
        const token = await getFCMToken();
        if (token) {
          const response = await this.$api.post('/api/notifications/save-token', {
            token: token
          });
          this.$q.notify({
            color: 'positive',
            message: response.data.message || 'Notifications linked!',
            icon: 'notifications_active'
          });
        } else {
          this.$q.notify({
            color: 'warning',
            message: 'Could not get notification token. Check Firebase Web Push settings.'
          });
        }
      } catch (err) {
        console.error('Error enabling notifications:', err);
        const details = err instanceof Error ? err.message : '';
        this.$q.notify({
          color: 'negative',
          message: details
            ? `Failed to enable notifications: ${details}`
            : 'Failed to enable notifications.'
        });
      }
    },
  },

  async beforeMount() {
    this.loading = true;
    try {
      const preferredTheme =
        localStorage.getItem('darkMode') === null 
        ? 'auto' 
        : Boolean(Number(localStorage.getItem('darkMode')));
      this.$q.dark.set(preferredTheme);

      const aliveReq = this.$api.get('/api/alive');
      const meReq = this.optionallyFetchUser();
      const aliveResp = await aliveReq;
      if (aliveResp.data.status != 'ok') {
        this.errors = ['Service is unavailable'];
      }
      await meReq;
    } finally {
      this.loading = false;
    }
  },

  provide() {
    return {
      me: computed(() => this.me),
      forceRefresh: computed(() => this.forceRefresh),
    };
  },
  computed: {
    darkModeIcon: function () {
      return this.$q.dark.isActive ? 'wb_sunny' : 'brightness_2';
    },
  },
  watch: {
    '$route.fullPath'() {
      this.errors = [];
    },
  },
});
</script>
