<template>
  <q-page class="q-pa-lg public-events-page">
    <div class="row items-center justify-between q-mb-lg">
      <div>
        <div class="text-h5">Events</div>
        <div class="text-subtitle2 text-grey-7">Choose an event and sign up for sessions.</div>
      </div>
      <div class="row q-gutter-sm">
        <q-btn-toggle
          v-model="manualLanguage"
          toggle-color="primary"
          unelevated
          dense
          :options="[
            { label: 'EN', value: 'en' },
            { label: 'NL', value: 'nl' },
          ]"
          @update:model-value="saveManualLanguage"
        />
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
                <div
                  class="text-body2 text-grey-8 basic-formatted-text"
                  v-html="formatBasicText(selectedEvent.description || 'No description')"
                />
            </div>
            <q-btn flat color="primary" icon="arrow_back" label="Back to events" to="/" />
          </div>
        </q-card-section>
        <q-banner class="bg-blue-1 text-blue-10 q-mx-md q-mb-md" rounded>
          <div class="text-weight-medium">{{ attendanceBannerCopy.title }}</div>
          <div>
            {{ attendanceBannerCopy.body }}
          </div>
        </q-banner>
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
                    <div
                      v-if="table.description"
                      class="q-item__label q-item__label--caption basic-formatted-text"
                      v-html="formatBasicText(table.description)"
                    />
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
                            <div
                              v-if="session.short_description"
                              class="text-body2 q-mt-sm basic-formatted-text"
                              v-html="formatBasicText(session.short_description)"
                            />
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
            <div
              class="text-body2 text-grey-8 basic-formatted-text"
              v-html="formatBasicText(event.description || 'No description')"
            />
            <div class="text-caption text-grey-7 q-mt-sm">{{ event.days.length }} day{{ event.days.length === 1 ? '' : 's' }}</div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <q-dialog v-model="signupInfoDialog.open" persistent>
      <q-card>
        <q-card-section>
          <div class="text-h6">{{ signupInfoCopy.title }}</div>
          <div class="text-body2 q-mt-sm">{{ signupInfoCopy.intro }}</div>
          <div class="q-mt-md text-body2">
            <ul class="q-pl-md q-my-none">
              <li>{{ signupInfoCopy.reminder }}</li>
              <li>{{ signupInfoCopy.waitlist }}</li>
              <li>{{ signupInfoCopy.attendance }}</li>
            </ul>
          </div>
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md q-gutter-sm">
          <q-btn flat :label="signupInfoCopy.skipLabel" @click="declineSignupInfo" />
          <q-btn
            color="primary"
            icon="notifications_active"
            :label="signupInfoCopy.enableLabel"
            @click="acceptSignupInfo"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="overlapDialog.open" persistent>
      <q-card>
        <q-card-section>
          <div class="text-h6">Already placed at this time</div>
          <div class="text-body2 q-mt-sm">
            You are already placed in "{{ overlapDialog.currentTitle }}" at this time. Do you want to switch to "{{ overlapDialog.targetTitle }}"?
          </div>
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md q-gutter-sm">
          <q-btn flat label="Keep current session" @click="resolveOverlapDialog(false)" />
          <q-btn color="primary" label="Switch sessions" @click="resolveOverlapDialog(true)" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="switchWarningDialog.open" persistent>
      <q-card>
        <q-card-section>
          <div class="text-h6">Switch warning</div>
          <div class="text-body2 q-mt-sm">
            Switching may move you from a placed spot to the waiting list. Continue?
          </div>
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md q-gutter-sm">
          <q-btn flat label="Cancel" @click="resolveSwitchWarningDialog(false)" />
          <q-btn color="warning" label="Switch anyway" @click="resolveSwitchWarningDialog(true)" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="secondSignupDialog.open" persistent>
      <q-card>
        <q-card-section>
          <div class="text-h6">Second signup will be waitlist</div>
          <div class="text-body2 q-mt-sm">
            You already have a placed session this day. A second signup will be added to the waiting list. Do you want to join waitlist or switch sessions?
          </div>
          <q-option-group
            v-model="secondSignupDialog.choice"
            class="q-mt-md"
            type="radio"
            :options="[
              { label: 'Join this session as waitlist', value: 'waitlist' },
              { label: 'Switch from current placed session to this session', value: 'switch' },
            ]"
          />
        </q-card-section>
        <q-card-actions align="right" class="q-pa-md q-gutter-sm">
          <q-btn flat label="Cancel" @click="resolveSecondSignupDialog(null)" />
          <q-btn color="primary" label="Continue" @click="resolveSecondSignupDialog(secondSignupDialog.choice)" />
        </q-card-actions>
      </q-card>
    </q-dialog>

  </q-page>
</template>

<script lang="ts">
import { defineComponent, inject } from 'vue';
import { formatBasicText as renderBasicText } from '../util/common';
import { enablePushNotifications } from '../lib/fcm';

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
  placement_mode?: string;
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
      manualLanguage: 'en' as 'en' | 'nl',
      signupInfoDialog: {
        open: false,
        pending: null as null | { event: PublicEvent; day: PublicDay; session: PublicSession },
      },
      overlapDialog: {
        open: false,
        currentTitle: '',
        targetTitle: '',
        resolve: null as null | ((value: boolean) => void),
      },
      switchWarningDialog: {
        open: false,
        resolve: null as null | ((value: boolean) => void),
      },
      secondSignupDialog: {
        open: false,
        choice: 'waitlist' as 'waitlist' | 'switch',
        resolve: null as null | ((value: 'waitlist' | 'switch' | null) => void),
      },
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
    effectiveLanguage(): 'en' | 'nl' {
      return this.manualLanguage;
    },
    signupInfoCopy() {
      const isDutch = this.effectiveLanguage === 'nl';
      if (isDutch) {
        return {
          title: 'Pushmeldingen voor dit event',
          intro: 'Wil je pushmeldingen inschakelen voor deze inschrijving?',
          reminder: 'Je krijgt een herinnering 1 dag en 30 minuten voordat de sessie begint.',
          waitlist: 'Je krijgt ook een melding als je van de wachtlijst naar een plek in de sessie wordt verplaatst.',
          attendance: 'We verwachten dat iedereen minstens 5 minuten van tevoren aanwezig is. Ben je niet op tijd, dan kunnen we je uit de sessie halen en de plek geven aan iemand van de wachtlijst die beschikbaar is.',
          enableLabel: 'Enable Push notifications',
          skipLabel: 'Not now',
        };
      }
      return {
        title: 'Push notifications for this event',
        intro: 'Would you like to enable push notifications for this signup?',
        reminder: 'You will get a reminder 1 day and 30 minutes before the session starts.',
        waitlist: 'You will also get a notification if you move from the waiting list into a spot in the session.',
        attendance: 'Please arrive at least 5 minutes early. If you are not there in time, we may remove you from the session and give the place to someone on the waiting list who is ready.',
        enableLabel: 'Enable Push notifications',
        skipLabel: 'Not now',
      };
    },
    attendanceBannerCopy() {
      const isDutch = this.effectiveLanguage === 'nl';
      if (isDutch) {
        return {
          title: 'Kom op tijd',
          body: 'We verwachten dat iedereen minstens 5 minuten van tevoren aanwezig is. Ben je niet op tijd, dan kunnen we je uit de sessie halen en de plek geven aan iemand van de wachtlijst die beschikbaar is.',
        };
      }
      return {
        title: 'Please arrive early',
        body: "We expect everyone to show up at least 5 minutes in advance. If you're not there in time, we may remove you from the session and give the place to someone on the waiting list who is ready.",
      };
    },
  },
  async beforeMount() {
    this.manualLanguage = this.loadPreferredLanguage();
    await this.fetchEvents();
  },
  methods: {
    signupPromptStorageKey() {
      return 'signup-notification-prompt-seen';
    },
    hasSeenSignupPrompt() {
      return localStorage.getItem(this.signupPromptStorageKey()) === '1';
    },
    markSignupPromptSeen() {
      localStorage.setItem(this.signupPromptStorageKey(), '1');
    },
    shouldShowSignupPrompt() {
      return this.$q.screen.lt.md && !this.hasSeenSignupPrompt();
    },
    browserLanguage() {
      if (typeof navigator === 'undefined') {
        return 'en';
      }
      const raw = (navigator.languages && navigator.languages[0]) || navigator.language || 'en';
      return String(raw).toLowerCase();
    },
    languageStorageKey() {
      return 'public-events-language';
    },
    loadPreferredLanguage(): 'en' | 'nl' {
      const saved = localStorage.getItem(this.languageStorageKey());
      if (saved === 'en' || saved === 'nl') {
        return saved;
      }
      return this.browserLanguage().startsWith('nl') ? 'nl' : 'en';
    },
    saveManualLanguage(value: string | number | null) {
      const normalized = value === 'nl' ? 'nl' : 'en';
      this.manualLanguage = normalized;
      localStorage.setItem(this.languageStorageKey(), normalized);
    },
    openSignupInfoDialog(event: PublicEvent, day: PublicDay, session: PublicSession) {
      this.signupInfoDialog.pending = { event, day, session };
      this.signupInfoDialog.open = true;
    },
    async acceptSignupInfo() {
      const pending = this.signupInfoDialog.pending;
      this.signupInfoDialog.open = false;
      if (!pending) {
        return;
      }
      this.markSignupPromptSeen();
      this.signupInfoDialog.pending = null;
      await enablePushNotifications(this.$api, this.$q);
      await this.requestSignup(pending.event, pending.day, pending.session, true);
    },
    async declineSignupInfo() {
      const pending = this.signupInfoDialog.pending;
      this.signupInfoDialog.open = false;
      if (!pending) {
        return;
      }
      this.markSignupPromptSeen();
      this.signupInfoDialog.pending = null;
      await this.requestSignup(pending.event, pending.day, pending.session, true);
    },
    promptOverlapDialog(overlapTitle: string, targetTitle: string) {
      this.overlapDialog.currentTitle = overlapTitle;
      this.overlapDialog.targetTitle = targetTitle;
      this.overlapDialog.open = true;
      return new Promise<boolean>((resolve) => {
        this.overlapDialog.resolve = resolve;
      });
    },
    resolveOverlapDialog(value: boolean) {
      const resolver = this.overlapDialog.resolve;
      this.overlapDialog.resolve = null;
      this.overlapDialog.open = false;
      if (resolver) {
        resolver(value);
      }
    },
    promptSwitchWarningDialog() {
      this.switchWarningDialog.open = true;
      return new Promise<boolean>((resolve) => {
        this.switchWarningDialog.resolve = resolve;
      });
    },
    resolveSwitchWarningDialog(value: boolean) {
      const resolver = this.switchWarningDialog.resolve;
      this.switchWarningDialog.resolve = null;
      this.switchWarningDialog.open = false;
      if (resolver) {
        resolver(value);
      }
    },
    promptSecondSignupDialog() {
      this.secondSignupDialog.choice = 'waitlist';
      this.secondSignupDialog.open = true;
      return new Promise<'waitlist' | 'switch' | null>((resolve) => {
        this.secondSignupDialog.resolve = resolve;
      });
    },
    resolveSecondSignupDialog(value: 'waitlist' | 'switch' | null) {
      const resolver = this.secondSignupDialog.resolve;
      this.secondSignupDialog.resolve = null;
      this.secondSignupDialog.open = false;
      if (resolver) {
        resolver(value);
      }
    },
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
    formatSessionMeta(session: PublicSession) {
      return `${session.start_time?.slice(0, 5)} • ${session.duration_minutes}m `;
    },
    formatBasicText(text: string | null | undefined) {
      return renderBasicText(text);
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
    async requestSignup(event: PublicEvent, day: PublicDay, session: PublicSession, skipSignupInfoPrompt = false) {
      if (!skipSignupInfoPrompt && this.shouldShowSignupPrompt()) {
        this.openSignupInfoDialog(event, day, session);
        return;
      }

      const placedSessions = (day.sessions || []).filter((s) => s.id !== session.id && s.my_status === 'placed');
      const overlap = placedSessions.find((s) => this.sessionOverlaps(s, session));

      if (overlap) {
        const confirmed = await this.promptOverlapDialog(overlap.title, session.title);
        if (!confirmed) {
          return;
        }
        const likelyWaitlist = event.placement_mode === 'delayed' || session.placed_count >= session.max_players;
        if (likelyWaitlist) {
          const proceed = await this.promptSwitchWarningDialog();
          if (!proceed) {
            return;
          }
        }
        await this.switchSession(overlap.id, session.id);
        return;
      }

      if (placedSessions.length > 0) {
        const choice = await this.promptSecondSignupDialog();
        if (!choice) {
          return;
        }
        if (choice === 'switch') {
          const source = placedSessions[0];
          const likelyWaitlist = event.placement_mode === 'delayed' || session.placed_count >= session.max_players;
          if (likelyWaitlist) {
            const proceed = await this.promptSwitchWarningDialog();
            if (!proceed) {
              return;
            }
          }
          await this.switchSession(source.id, session.id);
        } else {
          await this.signup(session.id);
        }
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

.event-card:hover {
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

.table-session-card {
  background: rgba(165, 165, 165, 0.44);
}

:global(.body--dark) .table-session-card {
  background: rgba(18, 25, 32, 0.42);
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
