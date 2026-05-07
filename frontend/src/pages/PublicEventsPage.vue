<template>
  <q-page class="q-pa-lg public-events-page">
    <div class="row items-center justify-between q-mb-lg">
      <div>
        <div class="text-h5">Public Session Signup</div>
        <div class="text-subtitle2 text-grey-7">Pick any session and sign up with one click.</div>
      </div>
      <q-btn color="primary" icon="refresh" label="Refresh" :loading="loading" @click="fetchEvents" />
    </div>

    <q-banner v-if="!me" class="bg-warning text-black q-mb-md" rounded>
      Please log in to sign up for sessions.
    </q-banner>

    <div v-if="loading" class="column items-center q-mt-xl">
      <q-spinner size="xl" />
      <div class="text-subtitle1 q-mt-md">Loading events...</div>
    </div>

    <q-banner v-else-if="events.length === 0" class="bg-info text-white q-mb-md" rounded>
      No upcoming events with sessions were found.
    </q-banner>

    <div v-else class="column q-gutter-md">
      <q-card v-for="event in events" :key="event.id" flat bordered>
        <q-card-section>
          <div class="text-h6">{{ event.title }}</div>
          <div class="text-body2 text-grey-8">{{ event.description || 'No description' }}</div>
        </q-card-section>

        <q-separator />

        <q-card-section class="column q-gutter-md">
          <div v-for="day in sortedDays(event.days)" :key="day.id" class="day-block">
            <div class="text-subtitle1">{{ formatDay(day) }}</div>
            <div class="row q-col-gutter-md q-mt-sm">
              <div v-for="session in sortedSessions(day.sessions)" :key="session.id" class="col-12 col-lg-6">
                <q-card flat bordered>
                  <q-card-section>
                    <div class="row items-start justify-between q-col-gutter-sm">
                      <div class="col">
                        <div class="text-subtitle1">{{ session.title }}</div>
                        <div class="text-caption text-grey-7 q-mt-xs">
                          {{ formatSessionMeta(session, day) }}
                        </div>
                        <div class="text-body2 q-mt-sm">{{ session.short_description }}</div>
                        <div class="q-mt-sm text-caption">
                          Seats: {{ session.placed_count }}/{{ session.max_players }} placed
                          <span class="q-ml-sm">Waitlist: {{ session.waitlist_count }}</span>
                        </div>
                      </div>
                      <div class="column q-gutter-xs">
                        <q-chip
                          v-if="session.my_status"
                          dense
                          :color="statusColor(session.my_status)"
                          text-color="white"
                        >
                          {{ statusLabel(session.my_status) }}
                        </q-chip>
                        <q-btn
                          v-if="!session.my_status"
                          color="primary"
                          icon="person_add"
                          label="Sign up"
                          :loading="signupLoadingSessionId === session.id"
                          @click="signup(session.id)"
                        />
                        <q-btn
                          v-else
                          outline
                          color="negative"
                          icon="person_remove"
                          label="Cancel"
                          :loading="signupLoadingSessionId === session.id"
                          @click="cancelSignup(session.id)"
                        />
                      </div>
                    </div>
                  </q-card-section>
                </q-card>
              </div>
            </div>
          </div>
        </q-card-section>
      </q-card>
    </div>
  </q-page>
</template>

<script lang="ts">
import { defineComponent, inject } from 'vue';

type PublicSession = {
  id: number;
  title: string;
  short_description: string;
  table_name: string;
  start_time: string;
  duration_minutes: number;
  max_players: number;
  placement_mode: string;
  placed_count: number;
  waitlist_count: number;
  my_status: string | null;
};

type PublicDay = {
  id: number;
  date: string;
  label?: string | null;
  sessions: PublicSession[];
};

type PublicEvent = {
  id: number;
  title: string;
  description?: string | null;
  days: PublicDay[];
};

export default defineComponent({
  name: 'PublicEventsPage',
  setup() {
    return {
      me: inject('me') as any,
    };
  },
  data() {
    return {
      loading: false,
      signupLoadingSessionId: null as number | null,
      events: [] as PublicEvent[],
    };
  },
  async beforeMount() {
    await this.fetchEvents();
  },
  methods: {
    async fetchEvents() {
      this.loading = true;
      try {
        this.events = (await this.$api.get('/api/events/public')).data || [];
      } catch (error) {
        this.$q.notify({
          type: 'negative',
          message: this.$extractErrors(error).join(', ') || 'Failed to fetch public events',
        });
        this.events = [];
      } finally {
        this.loading = false;
      }
    },
    sortedDays(days: PublicDay[]) {
      return [...(days || [])].sort((a, b) => (a.date || '').localeCompare(b.date || ''));
    },
    sortedSessions(sessions: PublicSession[]) {
      return [...(sessions || [])].sort((a, b) => (a.start_time || '').localeCompare(b.start_time || ''));
    },
    formatDay(day: PublicDay) {
      if (!day?.date) return day?.label || 'Day';
      const d = new Date(`${day.date}T00:00:00`);
      const dateLabel = d.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' });
      return day.label ? `${day.label} (${dateLabel})` : dateLabel;
    },
    formatSessionMeta(session: PublicSession, _day: PublicDay) {
      return `${session.start_time?.slice(0, 5)} • ${session.duration_minutes}m • ${session.table_name} • ${session.placement_mode}`;
    },
    statusLabel(status: string) {
      if (status === 'placed') return 'Placed';
      if (status === 'waitlist') return 'Waitlist';
      if (status === 'blocked_conflict') return 'Conflict';
      if (status === 'cancelled') return 'Cancelled';
      return status;
    },
    statusColor(status: string) {
      if (status === 'placed') return 'positive';
      if (status === 'waitlist') return 'warning';
      if (status === 'blocked_conflict') return 'negative';
      return 'grey';
    },
    async signup(sessionId: number) {
      this.signupLoadingSessionId = sessionId;
      try {
        await this.$api.post(`/api/event-sessions/${sessionId}/signup`);
        this.$q.notify({ type: 'positive', message: 'Signed up successfully' });
        await this.fetchEvents();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Signup failed' });
      } finally {
        this.signupLoadingSessionId = null;
      }
    },
    async cancelSignup(sessionId: number) {
      this.signupLoadingSessionId = sessionId;
      try {
        await this.$api.delete(`/api/event-sessions/${sessionId}/signup`);
        this.$q.notify({ type: 'positive', message: 'Signup cancelled' });
        await this.fetchEvents();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Cancel failed' });
      } finally {
        this.signupLoadingSessionId = null;
      }
    },
  },
});
</script>

<style scoped>
.day-block + .day-block {
  margin-top: 16px;
}
</style>
