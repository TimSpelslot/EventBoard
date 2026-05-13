<template>
  <q-layout view="lHh Lpr lFf">
    <q-header elevated>
      <q-toolbar class="row justify-between">
        <div class="q-gutter-x-md">
          <q-btn label="Events" icon="home" to="/" />
        </div>
        <q-avatar icon="img:spelslot-logo.svg" size="50px"></q-avatar>
        <div class="q-gutter-x-sm">
          <q-btn icon="notifications" color="primary" @click="setupNotifications" />
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
                <q-item v-if="me?.privilege_level >= 2" to="/admin/users">
                  <q-item-section>Approve users</q-item-section>
                </q-item>
                <q-item clickable v-close-popup @click="logout">
                  <q-item-section>Log out</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
          <template v-else>
            <q-btn label="Login" @click="login" icon="login" />
            <q-btn label="Log in as guest" @click="openGuestLoginDialog" icon="person" />
          </template>
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
      />
      <q-dialog v-model="guestLoginDialog.open">
        <q-card>
          <q-form @submit="loginAsGuest">
            <q-card-section class="q-gutter-md">
              <div class="text-h6">Log in as guest</div>
              <q-input
                v-model="guestLoginDialog.display_name"
                label="Name"
                autofocus
                :disable="guestLoginDialog.loading"
              />
              <q-input
                v-model="guestLoginDialog.email"
                label="Email (optional)"
                type="email"
                :disable="guestLoginDialog.loading"
              />
            </q-card-section>
            <q-card-actions align="right" class="q-pa-md q-gutter-sm">
              <q-btn flat label="Cancel" v-close-popup :disable="guestLoginDialog.loading" />
              <q-btn color="primary" label="Continue" type="submit" :loading="guestLoginDialog.loading" />
            </q-card-actions>
          </q-form>
        </q-card>
      </q-dialog>
      <a href="https://github.com/SpelSlot-IT/AdventureBoard" class="fixed-bottom-right q-mr-sm">
        <q-icon name="img:https://github.com/favicon.ico" size="lg" class="bg-grey-5" />
      </a>
    </q-page-container>
  </q-layout>
</template>

<script lang="ts">
import { defineComponent, computed } from 'vue';
import { isAxiosError } from 'axios';
import { enablePushNotifications } from '../lib/fcm';

export default defineComponent({
  name: 'MainLayout',

  data() {
    return {
      loading: true,
      errors: [] as string[],
      forceRefresh: 1,
      me: null as null | {
        id: number;
        display_name: string;
        privilege_level: number;
        profile_pic: string | null;
      },
      guestLoginDialog: {
        open: false,
        loading: false,
        display_name: '',
        email: '',
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
    openGuestLoginDialog() {
      this.guestLoginDialog.open = true;
      this.guestLoginDialog.loading = false;
      this.guestLoginDialog.display_name = '';
      this.guestLoginDialog.email = '';
    },
    async loginAsGuest() {
      const displayName = this.guestLoginDialog.display_name.trim();
      const email = this.guestLoginDialog.email.trim();
      if (!displayName) {
        this.$q.notify({
          type: 'negative',
          message: 'Name is required',
        });
        return;
      }

      this.guestLoginDialog.loading = true;
      try {
        await this.$api.post('/api/login/guest', {
          display_name: displayName,
          email: email || null,
        });
        await this.fetchMe();
        this.guestLoginDialog.open = false;
        this.$q.notify({
          type: 'positive',
          message: 'Logged in as guest',
        });
      } catch (error) {
        this.$q.notify({
          type: 'negative',
          message: this.$extractErrors(error).join(', ') || 'Guest login failed',
        });
      } finally {
        this.guestLoginDialog.loading = false;
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
    async setupNotifications() {
      if (!this.me) {
        this.$q.notify({
          color: 'negative',
          message: 'You need to be logged in to enable notifications.',
          icon: 'error'
        });
        return;
      }
      await enablePushNotifications(this.$api, this.$q);
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
