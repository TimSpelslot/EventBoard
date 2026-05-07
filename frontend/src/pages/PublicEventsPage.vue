<template>
  <q-page class="q-pa-lg public-events-page">
    <div class="row items-center justify-between q-mb-lg">
      <div>
        <div class="text-h5">Events</div>
        <div class="text-subtitle2 text-grey-7">Choose an event and sign up for sessions.</div>
      </div>
      <div class="row q-gutter-sm">
        <q-btn
          v-if="me?.privilege_level >= 2"
          color="secondary"
          icon="edit_calendar"
          label="Manage Events"
          to="/admin/events"
        />
        <q-btn color="primary" icon="refresh" label="Refresh" :loading="loading" @click="fetchEvents" />
      </div>
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

    <div v-else-if="selectedEvent" class="column q-gutter-md">
      <q-card flat bordered>
        <q-img v-if="selectedEvent.image_url" :src="selectedEvent.image_url" style="height: 220px" />
        <q-card-section>
          <div class="row items-center justify-between q-gutter-sm">
            <div>
              <div class="text-h6">{{ selectedEvent.title }}</div>
              <div class="text-body2 text-grey-8">{{ selectedEvent.description || 'No description' }}</div>
            </div>
            <q-btn flat color="primary" icon="arrow_back" label="Back to events" to="/" />
          </div>
        </q-card-section>
        <q-separator />
        <q-card-section class="column q-gutter-md">
          <div v-for="day in sortedDays(selectedEvent.days)" :key="day.id" class="day-block">
            <div class="text-subtitle1">{{ formatDay(day) }}</div>
            <q-list bordered class="q-mt-sm rounded-borders">
              <q-expansion-item
                v-for="table in groupedTables(day.sessions)"
                :key="`${day.id}-${table.id}`"
                :model-value="isTableExpanded(day.id, table.id)"
                @update:model-value="(v) => setTableExpanded(day.id, table.id, !!v)"
                expand-separator
                :header-class="$q.dark.isActive ? 'table-header-dark' : 'table-header-light'"
              >
                <template #header>
                  <q-item-section>
                    <q-item-label class="text-subtitle2">{{ table.name }}</q-item-label>
                    <q-item-label caption>{{ table.sessions.length }} session{{ table.sessions.length === 1 ? '' : 's' }}</q-item-label>
                    <q-item-label v-if="table.description" caption>{{ table.description }}</q-item-label>
                  </q-item-section>
                  <q-item-section side v-if="table.image_url">
                    <q-avatar rounded size="42px" class="table-thumb">
                      <img :src="table.image_url" alt="Table" />
                    </q-avatar>
                  </q-item-section>
                </template>

                <q-card flat class="table-sessions-panel" :style="tableBackgroundStyle(table)">
                  <q-card-section class="q-gutter-sm">
                    <q-card v-for="session in table.sessions" :key="session.id" flat bordered class="table-session-card">
                      <q-card-section>
                        <div class="row items-start justify-between q-col-gutter-sm">
                          <div class="col">
                            <div class="text-subtitle1">{{ session.title }}</div>
                            <div class="text-caption text-body2 q-mt-sm">
                              {{ formatSessionMeta(session, day) }}
                            </div>
                            <div v-if="session.short_description" class="text-body2 q-mt-sm">{{ session.short_description }}</div>
                            <div v-if="session.gamemaster_name" class="text-caption q-mt-xs">Gamemaster: {{ session.gamemaster_name }}</div>
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
                              @click="requestSignup(selectedEvent, day, session)"
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
                  </q-card-section>
                </q-card>
              </q-expansion-item>
            </q-list>
          </div>
        </q-card-section>
      </q-card>
    </div>
    <div v-else class="row q-col-gutter-md justify-center">
      <div v-for="event in events" :key="event.id" class="col-12 col-sm-6 col-lg-4 col-xl-3">
        <q-card class="event-card cursor-pointer" flat bordered @click="$router.push(`/events/${event.id}`)">
          <q-img v-if="event.image_url" :src="event.image_url" style="height: 180px" />
          <q-card-section>
            <div class="text-h6">{{ event.title }}</div>
            <div class="text-body2 text-grey-8">{{ event.description || 'No description' }}</div>
            <div class="text-caption text-grey-7 q-mt-sm">{{ event.days.length }} day{{ event.days.length === 1 ? '' : 's' }}</div>
          </q-card-section>
        </q-card>
      </div>
    </div>
  </q-page>
</template>

<script lang="ts">
import { defineComponent, inject } from 'vue';

type PublicSession = {
  id: number;
  title: string;
  short_description: string | null;
  gamemaster_name: string | null;
  event_table_id: number;
  table_name: string;
  table_description: string | null;
  table_image_url: string | null;
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
  image_url?: string | null;
  days: PublicDay[];
};

export default defineComponent({
  name: 'PublicEventsPage',
  props: {
    eventId: {
      type: [String, Number],
      required: false,
      default: null,
    },
  },
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
      expandedTables: {} as Record<string, boolean>,
    };
  },
  computed: {
    selectedEvent(): PublicEvent | null {
      if (!this.eventId) {
        return null;
      }
      const target = Number(this.eventId);
      return this.events.find((e) => e.id === target) || null;
    },
  },
  async beforeMount() {
    await this.fetchEvents();
  },
  methods: {
        groupedTables(sessions: PublicSession[]) {
          const grouped = new Map<number, { id: number; name: string; description: string | null; image_url: string | null; sessions: PublicSession[] }>();
          for (const session of sessions || []) {
            const key = session.event_table_id;
            if (!grouped.has(key)) {
              grouped.set(key, {
                id: key,
                name: session.table_name || `Table ${key}`,
                description: session.table_description || null,
                image_url: session.table_image_url || null,
                sessions: [],
              });
            }
            grouped.get(key)!.sessions.push(session);
          }
          return [...grouped.values()]
            .map((table) => ({
              ...table,
              sessions: this.sortedSessions(table.sessions),
            }))
            .sort((a, b) => a.name.localeCompare(b.name));
        },
    tableExpansionKey(dayId: number, tableId: number) {
      return `${dayId}-${tableId}`;
    },
    isTableExpanded(dayId: number, tableId: number) {
      return !!this.expandedTables[this.tableExpansionKey(dayId, tableId)];
    },
    setTableExpanded(dayId: number, tableId: number, value: boolean) {
      const key = this.tableExpansionKey(dayId, tableId);
      this.expandedTables = {
        ...this.expandedTables,
        [key]: value,
      };
    },
    tableBackgroundStyle(table: { image_url: string | null }) {
      if (!table.image_url) {
        return {};
      }
      const overlay = this.$q.dark.isActive
        ? 'linear-gradient(rgba(146, 146, 146, 0.1), rgba(18,22,28,0.1))'
        : 'linear-gradient(rgba(170, 170, 170, 0.2), rgba(255,255,255,0.1))';
      return {
        backgroundImage: `${overlay}, url(${table.image_url})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      };
    },
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
      return `${session.start_time?.slice(0, 5)} • ${session.duration_minutes}m `;
    },
    statusLabel(status: string) {
      if (status === 'placed') return 'Placed';
      if (status === 'waitlist') return 'Waitlist';
      if (status === 'blocked_conflict') return 'Waitlist';
      if (status === 'cancelled') return 'Cancelled';
      return status;
    },
    statusColor(status: string) {
      if (status === 'placed') return 'positive';
      if (status === 'waitlist') return 'warning';
      if (status === 'blocked_conflict') return 'warning';
      return 'grey';
    },
    sessionOverlaps(a: PublicSession, b: PublicSession) {
      const [ah, am] = a.start_time.slice(0, 5).split(':').map(Number);
      const [bh, bm] = b.start_time.slice(0, 5).split(':').map(Number);
      const aStart = ah * 60 + am;
      const bStart = bh * 60 + bm;
      const aEnd = aStart + a.duration_minutes;
      const bEnd = bStart + b.duration_minutes;
      return aStart < bEnd && bStart < aEnd;
    },
    async requestSignup(event: PublicEvent, day: PublicDay, session: PublicSession) {
      const placedSessions = (day.sessions || []).filter((s) => s.id !== session.id && s.my_status === 'placed');
      const overlap = placedSessions.find((s) => this.sessionOverlaps(s, session));

      if (overlap) {
        this.$q.dialog({
          title: 'Already placed at this time',
          message: `You are already placed in "${overlap.title}" at this time. Do you want to switch to "${session.title}"?`,
          cancel: { label: 'Keep current session' },
          ok: { label: 'Switch sessions', color: 'primary' },
          persistent: true,
        }).onOk(async () => {
          const likelyWaitlist = event.placement_mode === 'delayed' || session.placed_count >= session.max_players;
          if (likelyWaitlist) {
            const proceed = await new Promise<boolean>((resolve) => {
              this.$q.dialog({
                title: 'Switch warning',
                message: 'Switching may move you from a placed spot to the waiting list. Continue?',
                cancel: true,
                ok: { label: 'Switch anyway', color: 'warning' },
                persistent: true,
              }).onOk(() => resolve(true)).onCancel(() => resolve(false));
            });
            if (!proceed) {
              return;
            }
          }
          await this.switchSession(overlap.id, session.id);
        });
        return;
      }

      if (placedSessions.length > 0) {
        this.$q.dialog({
          title: 'Second signup will be waitlist',
          message: 'You already have a placed session this day. A second signup will be added to the waiting list. Do you want to join waitlist or switch sessions?',
          options: {
            type: 'radio',
            model: 'waitlist',
            items: [
              { label: 'Join this session as waitlist', value: 'waitlist' },
              { label: 'Switch from current placed session to this session', value: 'switch' },
            ],
          },
          cancel: true,
          ok: { label: 'Continue', color: 'primary' },
          persistent: true,
        }).onOk(async (choice: string) => {
          if (choice === 'switch') {
            const source = placedSessions[0];
            const likelyWaitlist = event.placement_mode === 'delayed' || session.placed_count >= session.max_players;
            if (likelyWaitlist) {
              const proceed = await new Promise<boolean>((resolve) => {
                this.$q.dialog({
                  title: 'Switch warning',
                  message: 'Switching may move you from a placed spot to the waiting list. Continue?',
                  cancel: true,
                  ok: { label: 'Switch anyway', color: 'warning' },
                  persistent: true,
                }).onOk(() => resolve(true)).onCancel(() => resolve(false));
              });
              if (!proceed) {
                return;
              }
            }
            await this.switchSession(source.id, session.id);
          } else {
            await this.signup(session.id);
          }
        });
        return;
      }

      await this.signup(session.id);
    },
    async switchSession(fromSessionId: number, toSessionId: number) {
      this.signupLoadingSessionId = toSessionId;
      try {
        await this.$api.delete(`/api/event-sessions/${fromSessionId}/signup`);
        await this.$api.post(`/api/event-sessions/${toSessionId}/signup`);
        this.$q.notify({ type: 'positive', message: 'Session switched' });
        await this.fetchEvents();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to switch sessions' });
      } finally {
        this.signupLoadingSessionId = null;
      }
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

.event-card {
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.event-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.14);
}

.table-header-light {
  background: #eef3f7;
  color: #1c2430;
  align-items: flex-start;
  min-height: 84px;
  padding-top: 10px;
  padding-bottom: 10px;
}

.table-header-dark {
  background: #1f2b36;
  color: #f6fbff;
  align-items: flex-start;
  min-height: 84px;
  padding-top: 10px;
  padding-bottom: 10px;
}

.table-header-light :deep(.q-item__section--main),
.table-header-dark :deep(.q-item__section--main) {
  padding-right: 12px;
}

.table-header-light :deep(.q-item__label),
.table-header-dark :deep(.q-item__label) {
  white-space: normal;
}

.table-header-light :deep(.q-item__label--caption),
.table-header-dark :deep(.q-item__label--caption) {
  line-height: 1.35;
}

.table-thumb {
  align-self: flex-start;
  border: 1px solid rgba(255, 255, 255, 0.4);
}

.table-sessions-panel {
  backdrop-filter: blur(1px);
}

.table-session-card {
  background: rgba(165, 165, 165, 0.44);
}

:global(.body--dark) .table-session-card {
  background: rgba(18, 25, 32, 0.42);
  backdrop-filter: blur(2px);
  border-color: rgba(180, 205, 230, 0.22);
}

:global(.body--dark) .table-session-card .text-subtitle1,
:global(.body--dark) .table-session-card .text-body2,
:global(.body--dark) .table-session-card .text-caption {
  color: #cee3ff;
}

:global(.body--dark) .table-sessions-panel {
  border-top: 1px solid rgba(185, 210, 232, 0.16);
}
</style>
