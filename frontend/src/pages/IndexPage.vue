<template>
  <q-page class="page-bottom-spacing">
    <div class="row items-center justify-center q-my-md q-mx-lg">
      <q-btn
        v-if="showWeekNavigation && canGoEarlier"
        icon="chevron_left"
        :aria-label="labels.earlier"
        color="primary"
        @click="switchWeek(-1)"
        ><span class="gt-sm">{{ labels.earlier }}</span>
      </q-btn>
      <div class="text-h6 col-6 text-center">{{ eventTypeTitle || 'Event' }} - {{ displayDateLabel }}</div>
      <q-btn
        v-if="showWeekNavigation"
        icon-right="chevron_right"
        :aria-label="labels.later"
        color="primary"
        @click="switchWeek(1)"
        ><span class="gt-sm">{{ labels.later }}</span>
      </q-btn>
    </div>
    <q-banner v-if="me" class="bg-info text-white q-mx-lg q-mb-md" rounded>
      {{ labels.assignmentNotice }}
    </q-banner>
    <div v-if="loading" class="column flex flex-center q-my-xl">
      <q-spinner size="xl" />
      <div class="text-h6 q-mt-md text-center">{{ labels.loading }}</div>
    </div>
    <q-card v-else-if="adventures.length == 0" class="q-mx-lg">
      <q-card-section class="text-center">
        {{ labels.noSessions }}
      </q-card-section>
    </q-card>
    <div v-else class="row justify-evenly q-col-gutter-lg">
      <div
        :class="(isInAdventure(a, me?.id) ? 'order-first' : '') + ' col-xs-12 col-sm-6 col-md-4 col-lg-3'"
        v-for="a in adventures"
        :key="a.id"
      >
        <q-card v-if="!isWaitinglist(a)" class="q-ma-md">
          <q-card-section class="q-gutter-md">
            <q-btn
              v-if="me && (me.id == a.user_id || me.privilege_level >= 2)"
              icon="edit"
              round
              color="accent"
              @click="
                editAdventure = a;
                addAdventure = true;
              "
              class="float-right"
            />
            <div class="text-h6 text-center">{{ a.title }}</div>
            <q-separator />

            <div class="row full-width justify-end">
              <q-chip
                v-for="t in a.tags?.split(',')"
                :key="t"
                :label="t"
                color="accent"
                text-color="white"
                :ripple="false"
              />
            </div>
            <div class="description">
              <template v-if="a.short_description">
                 <div style="white-space: pre-line;">{{ a.short_description }}</div>
              </template>
              <i v-else>{{ labels.noDescription }}</i>
            </div>
            <q-list v-if="me?.privilege_level >= 2" class="adminDropTarget">
              <Container
                :class="[
                  'rounded-borders',
                  { 'grid-container': a.assignments.length > 0 },
                ]"
                @drop="(dr) => onDrop(dr, a.id)"
                group-name="assignedPlayers"
                :get-child-payload="
                  (n) => ({
                    from_adventure: a.id,
                    user_id: a.assignments[n].user.id,
                  })
                "
              >
                <template v-if="a.assignments.length > 0">
                  <Draggable v-for="p in a.assignments" :key="p.user.id">
                    <q-item class="items-center round-borders character">
                      <q-avatar size="sm" class="q-mr-sm">
                        <img :src="p.user.profile_pic" />
                      </q-avatar>
                        <div class="q-mr-sm">
                          {{ p.user.display_name }}
                        </div>
                      <q-btn
                        size="sm"
                        color="negative"
                        class="q-mr-sm flat"
                        icon="delete"
                        @click="cancelAssignment(a.id, p.user.id)"
                        round
                      />
                      <q-btn
                        size="sm"
                        :icon="p.appeared ? 'check' : 'close'"
                        round
                        :color="p.appeared ? 'positive' : 'negative'"
                        class="q-mr-sm flat"
                        @click="togglePresence(a.id, p)"
                      />
                      <q-btn flat round dense icon="castle" size="sm" color="primary">
                        <q-menu>
                          <q-list>
                            <q-item
                              v-for="targetAdv in adventures.filter((adv: any) => adv.id !== a.id)"
                              :key="targetAdv.id"
                              clickable
                              v-close-popup
                              @click="movePlayer(p.user.id, a.id, targetAdv.id)"
                            >
                              <q-item-section avatar>
                                <q-icon name="castle" color="primary" size="xs" />
                              </q-item-section>
                              <q-item-section>
                                {{ targetAdv.title }}
                              </q-item-section>
                            </q-item>
                          </q-list>
                        </q-menu>
                      </q-btn>
                    </q-item>
                  </Draggable>
                </template>
                <template v-else>
                  <q-item
                    class="text-subtitle1 text-center none-list non-selectable"
                  >
                    {{ labels.noPlayersAssigned }}
                  </q-item>
                </template>
              </Container>
            </q-list>
            <q-list v-else class="rounded-borders grid-container">
              <q-item class="items-center" v-for="p in a.assignments" :key="p.user.id">
                <q-avatar size="sm" class="q-mr-sm">
                  <img :src="p.user.profile_pic" />
                </q-avatar>
                <div class="default-text-color">{{ p.user.display_name }}</div>
                <q-btn
                  v-if="p.user.id == me?.id"
                  size="sm"
                  color="negative"
                  class="q-mr-sm flat"
                  icon="delete"
                  @click="cancelAssignment(a.id)"
                  round
                />
              </q-item>
            </q-list>
            <div class="row justify-between">
              <div>{{ labels.oneShot }}</div>
             </div>
            <div class="container">
              <div class="row justify-center q-gutter-sm" v-if="!isDateInPast(a)">
                <q-btn
                  v-for="n in 3"
                  style="max-width: 8rem"
                  :key="n"
                  icon="person_add"
                  :label="`${n}`"
                  color="primary"
                  :outline="mySignups[a.id] === n"
                  @click="signup(a, n)"
                />
              </div>
              <div class="row justify-center q-my-md">
                <q-btn
                  :label="labels.moreDetails"
                  icon="info"
                  @click="focussed = a"
                  color="primary"
                />
              </div>
            </div>
          </q-card-section>
        </q-card>
        <q-card v-else class="q-ma-md waitinglist">
          <q-card-section class="q-gutter-md">
            <div class="text-h6 text-center">{{ a.title }}</div>
            <q-separator />
            <q-list v-if="me?.privilege_level >= 2" class="adminDropTarget">
              <Container
                class="rounded-borders grid-container"
                @drop="(dr) => onDrop(dr, a.id)"
                group-name="assignedPlayers"
                :get-child-payload="
                  (n) => ({
                    from_adventure: a.id,
                    user_id: a.assignments[n].user.id,
                  })
                "
              >
                <Draggable v-for="p in a.assignments" :key="p.user.id">
                  <q-item class="items-center round-borders character">
                    <q-avatar size="sm" class="q-mr-sm">
                      <img :src="p.user.profile_pic" />
                    </q-avatar>
                    <div class="q-mr-sm">
                      {{ p.user.display_name }}
                    </div>
                    <q-btn
                      size="sm" 
                      color="negative"
                      class="q-mr-sm flat"
                      icon="delete"
                      @click="cancelAssignment(a.id, p.user.id)"
                      round
                    />
                    <q-btn flat round dense icon="castle" size="sm" color="primary">
                      <q-menu>
                        <q-list>
                          <q-item
                            v-for="targetAdv in adventures.filter((adv: any) => adv.id !== a.id)"
                            :key="targetAdv.id"
                            clickable
                            v-close-popup
                            @click="movePlayer(p.user.id, a.id, targetAdv.id)"
                          >
                            <q-item-section avatar>
                              <q-icon name="castle" color="primary" size="xs" />
                            </q-item-section>
                            <q-item-section>
                              {{ targetAdv.title }}
                            </q-item-section>
                          </q-item>
                        </q-list>
                      </q-menu>
                    </q-btn>
                  </q-item>
                </Draggable>
              </Container>
            </q-list>
            <q-list v-else class="rounded-borders grid-container">
              <q-item class="items-center" v-for="p in a.assignments" :key="p.user.id">
                <q-avatar size="sm" class="q-mr-sm">
                  <img :src="p.user.profile_pic" />
                </q-avatar>
                <div>
                  {{ p.user.display_name }}
                </div>
                <q-btn
                  v-if="p.user.id == me?.id"
                  size="sm"
                  color="negative"
                  class="q-mr-sm flat"
                  icon="delete"
                  @click="cancelAssignment(a.id)"
                />
              </q-item>
            </q-list>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <q-page-sticky position="bottom" :offset="[0, 18]">
      <q-btn
        v-if="me && me.privilege_level >= 1"
        fab
        :label="labels.makeAdventure"
        icon="add"
        color="accent"
        @click="
          editAdventure = null;
          addAdventure = true;
        "
      />
    </q-page-sticky>

    <q-dialog :modelValue="!!focussed" @hide="focussed = null">
      <q-card style="min-width: 300px">
        <q-card-section>
          <div class="text-h6">{{ focussed.title }}</div>
          <q-separator />
          <q-chip
            v-for="t in focussed.tags?.split(',')"
            :key="t"
            :label="t"
            color="accent"
            text-color="white"
            :ripple="false"
          />
          <q-markup-table flat class="q-mb-md">
            <tr>
              <td>DM</td>
              <td>{{ focussed.creator.display_name }}</td>
            </tr>
            <tr>
              <td>{{ labels.duration }}</td>
              <td>{{ labels.oneShot }}</td>
            </tr>
            <tr>
              <td>{{ labels.maxPlayers }}</td>
              <td>{{ focussed.max_players }}</td>
            </tr>
          </q-markup-table>
          <div class="description">
            <template v-if="focussed.short_description">{{
              focussed.short_description
            }}</template
            ><i v-else>{{ labels.noDescription }}</i>
          </div>
        </q-card-section>
        <template v-if="me?.privilege_level >= 2">
          <q-list >
            <q-item class="q-pa-md">{{ labels.signupsNotFinal }}</q-item>
            <Container class="rounded-borders grid-container">
              <q-item
                v-for="s in focussed.signups"
                :key="s.id"
                class="items-center"
              >
                <q-avatar size="sm" class="q-mr-sm">
                  <img :src="s.user?.profile_pic" />
                </q-avatar>
                <div class="q-mr-sm">
                  {{ s.user?.display_name }} - {{ choiceLabels[s.priority] }}
                </div>
              </q-item>
            </Container>
          </q-list>
        </template>
        
        <q-separator />
        <q-card-actions class="justify-end">
          <q-btn
            :label="labels.cancelSignup"
            color="negative"
            v-if="focussed.id in mySignups"
            class="q-mr-md"
            @click="signup(focussed, mySignups[focussed.id])"
          />
          <q-btn-dropdown
            split
            color="primary"
            :label="labels.signUp"
            content-class="q-px-lg"
            @click="signup(focussed, 1)"
            :loading="saving"
          >
            <q-list>
              <template v-for="n in [1, 2, 3]" :key="n">
                <q-item
                  clickable
                  v-close-popup
                  @click="signup(focussed, n)"
                  :disable="mySignups[focussed.id] == n"
                >
                  <q-item-section avatar v-if="focussed.id in mySignups">
                    <q-avatar
                      icon="check"
                      text-color="positive"
                      v-if="mySignups[focussed.id] == n"
                    />
                  </q-item-section>
                  <q-item-section>
                    <q-item-label>{{ choiceLabels[n] }}</q-item-label>
                  </q-item-section>
                </q-item>
              </template>
            </q-list>
          </q-btn-dropdown>
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="addAdventure" :persistent="addingAdventure">
      <div class="col-8">
        <AddAdventure
          @eventChange="eventChange"
          @canClose="(v) => (addingAdventure = !v)"
          :editExisting="editAdventure"
          :eventTypeId="Number(eventTypeId)"
          :defaultDate="selectedDate"
          :isSingleEvent="Boolean(selectedEventType?.is_single_event)"
        />
      </div>
    </q-dialog>
  </q-page>
</template>

<style lang="scss" scoped>
.description {
  background-color: var(--q-text-bg);
  border: 1px solid;
  border-radius: 4px;
  padding: 8px;
}
@media (max-width: 599px) {
  .page-bottom-spacing {
    padding-bottom: 80px;
  }
}
.adminDropTarget {
  border-radius: 4px;
  background-color: $secondary;
}
.character {
  border: 1px solid;
  border-radius: 4px;
  cursor: grab;
}
.waitinglist {
  background-color: var(--q-card-bg);
  height: 95%;
}
.grid-container {
  column-count: 2;
  column-gap: 12px;
}
.grid-container > * {
  break-inside: avoid;
}
</style>

<script lang="ts">
import { defineComponent, inject } from 'vue';
import { Container, Draggable } from 'vue3-smooth-dnd';
import AddAdventure from '../components/AddAdventure.vue';

const toLocalDateString = (d: Date): string => {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const fromDateString = (dateStr: string): Date => {
  const [year, month, day] = dateStr.split('-').map(Number);
  return new Date(year, month - 1, day);
};

export default defineComponent({
  name: 'IndexPage',
  components: { AddAdventure, Container, Draggable },
  emits: ['setErrors', 'startAdminAction', 'finishAdminAction'],
  props: {
    eventTypeId: {
      type: String,
      required: true,
    },
  },
  setup() {
    return {
      me: inject('me') as any,
      forceRefresh: inject('forceRefresh') as number,
    };
  },
  data() {
    const queryDate = (((this as any).$route?.query?.date as string) || '');
    const baseDate = /^\d{4}-\d{2}-\d{2}$/.test(queryDate)
      ? fromDateString(queryDate)
      : new Date();
    const monday = new Date(baseDate);
    monday.setDate(baseDate.getDate() - ((baseDate.getDay() + 6) % 7));
    return {
      weekStart: toLocalDateString(monday),
      adventures: [],
      focussed: null as any,
      addAdventure: false,
      addingAdventure: false,
      loading: false,
      saving: false,
      editAdventure: null,
      loadedSignups: false,
      mySignups: {} as { [adventure_id: number]: 1 | 2 | 3 },
      eventTypeTitle: '',
      selectedDate: queryDate,
      selectedEventType: null as any,
    };
  },
  methods: {
    isDutchEventTitle(title: string): boolean {
      const normalized = title.toLowerCase();
      return normalized.includes('jeugd') || normalized.includes('junior');
    },
    formatDutchDate(dateStr: string): string {
      const d = fromDateString(dateStr);
      return new Intl.DateTimeFormat('nl-NL', {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
      }).format(d);
    },
    ordinalDay(day: number): string {
      const mod10 = day % 10;
      const mod100 = day % 100;
      if (mod10 === 1 && mod100 !== 11) return `${day}st`;
      if (mod10 === 2 && mod100 !== 12) return `${day}nd`;
      if (mod10 === 3 && mod100 !== 13) return `${day}rd`;
      return `${day}th`;
    },
    formatEnglishDate(dateStr: string): string {
      const d = fromDateString(dateStr);
      const weekday = new Intl.DateTimeFormat('en-US', { weekday: 'long' }).format(d);
      const month = new Intl.DateTimeFormat('en-US', { month: 'long' }).format(d);
      return `${weekday} ${month} ${this.ordinalDay(d.getDate())}`;
    },
    getNthWeekdayOfMonth(year: number, monthIndex: number, weekday: number, weekOfMonth: number): Date | null {
      const firstDay = new Date(year, monthIndex, 1);
      const targetJsWeekday = (weekday + 1) % 7;
      const offset = (targetJsWeekday - firstDay.getDay() + 7) % 7;
      const dayNum = 1 + offset + (weekOfMonth - 1) * 7;
      const lastDay = new Date(year, monthIndex + 1, 0).getDate();
      if (dayNum > lastDay) {
        return null;
      }
      return new Date(year, monthIndex, dayNum);
    },
    getAdjacentSessionDate(offset: number): Date {
      const baseDate = /^\d{4}-\d{2}-\d{2}$/.test(this.selectedDate)
        ? fromDateString(this.selectedDate)
        : new Date();

      if (!this.isDutchEvent || !this.selectedEventType) {
        const d = new Date(baseDate);
        d.setDate(d.getDate() + offset * 7);
        return d;
      }

      const weekday = Number(this.selectedEventType.weekday);
      const weekOfMonth = Number(this.selectedEventType.week_of_month);
      const excludeJulyAugust = Boolean(this.selectedEventType.exclude_july_august);

      let year = baseDate.getFullYear();
      let monthIndex = baseDate.getMonth();
      for (let i = 0; i < 36; i += 1) {
        monthIndex += offset > 0 ? 1 : -1;
        if (monthIndex > 11) {
          monthIndex = 0;
          year += 1;
        }
        if (monthIndex < 0) {
          monthIndex = 11;
          year -= 1;
        }

        const month = monthIndex + 1;
        if (excludeJulyAugust && (month === 7 || month === 8)) {
          continue;
        }

        const candidate = this.getNthWeekdayOfMonth(year, monthIndex, weekday, weekOfMonth);
        if (candidate) {
          return candidate;
        }
      }

      const fallback = new Date(baseDate);
      fallback.setDate(fallback.getDate() + offset * 7);
      return fallback;
    },
    async fetch(reloadSignups: boolean) {
      if(!this.loadedSignups) {
        reloadSignups = true;
      }
      try {
        this.loading = true;
        const req1 = this.$api.get(
          '/api/adventures?week_start=' +
            this.weekStart +
            '&week_end=' +
            this.weekEnd +
            '&event_type_id=' +
            this.eventTypeId
        );
        if (this.me && reloadSignups) {
          const resp = await this.$api.get('/api/signups?user=' + this.me.id);
          this.mySignups = {};
          for (const { adventure_id, priority } of resp.data) {
            this.mySignups[adventure_id] = priority;
          }
        }
        const resp = await req1;
        this.adventures = resp.data;
        this.loadedSignups = true;
      } catch (e) {
        this.$emit('setErrors', this.$extractErrors(e));
      } finally {
        this.loading = false;
      }
    },
    async fetchEventTypeMeta() {
      const resp = await this.$api.get('/api/event-types');
      const selected = resp.data.find((et: any) => String(et.id) === String(this.eventTypeId));
      this.eventTypeTitle = selected?.title || '';
      this.selectedEventType = selected || null;
    },
    isDateInPast(a: {date: string}) {
      const currentDay = toLocalDateString(new Date());
      const sessionDay = toLocalDateString(fromDateString(a.date));
      return fromDateString(currentDay).getTime() > fromDateString(sessionDay).getTime();
    },
    async signup(e: { date: string; id: string }, prio: number) {
      try {
        this.saving = true;
        await this.$api.post('/api/signups', {
          adventure_id: e.id,
          priority: prio,
        });
        this.$q.notify({
          message: this.labels.signupSubmitted,
          type: 'positive',
        });
        await this.fetch(true);
      } finally {
        this.saving = false;
      }
    },
    eventChange() {
      this.addAdventure = false;
      this.fetch(false);
    },
    switchWeek(offset: number) {
      const targetDate = this.getAdjacentSessionDate(offset);
      this.selectedDate = toLocalDateString(targetDate);

      const monday = new Date(targetDate);
      monday.setDate(targetDate.getDate() - ((targetDate.getDay() + 6) % 7));
      this.weekStart = toLocalDateString(monday);

      this.$router.replace({
        query: {
          ...this.$route.query,
          date: this.selectedDate,
        },
      });
    },
    isWaitinglist(a: { is_waitinglist: number }): boolean {
      return a.is_waitinglist >= 1;
    },
    cancelAssignment(adventure_id: number, user_id?: number) {
      this.$q
        .dialog({
          title: this.labels.cancelAssignmentTitle,
          message:
            this.labels.cancelAssignmentMessage,
          cancel: true,
        })
        .onOk(async () => {
          const data: { adventure_id: number; user_id?: number } = {
            adventure_id,
          };
          if (user_id) {
            data.user_id = user_id;
          }
          await this.$api.request({
            method: 'DELETE',
            url: '/api/player-assignments',
            data,
            headers: { 'Content-Type': 'application/json' }
          });
          this.$q.notify({
            message: this.labels.cancelledAssignment,
            type: 'positive',
          });
          this.fetch(false);
        });
    },
    isInAdventure(a: any, id: any) {
      if (id === undefined) return false;
      if (!a.assignments) return false;
      for (const p of a.assignments) {
        if (p.user.id === id) {
          console.log("you're in session: ", a.title);
          return true
        };
      } 
      return false;
    },
    async togglePresence(adventure_id: number, assignment: any) {
      assignment.appeared = !assignment.appeared;
      await this.$api.post('/api/player-assignments', {
        adventure_id: adventure_id,
        user_id: assignment.user.id,
        appeared: assignment.appeared,
      });
    },
    async movePlayer(userId: number, fromAdventureId: number, toAdventureId: number) {
      const simulatedDropResult = {
        payload: {
          from_adventure: fromAdventureId,
          user_id: userId,
        },
        addedIndex: 0,
        removedIndex: null,
      };
      await this.onDrop(simulatedDropResult, toAdventureId);
    },
    async onDrop(
      dropResult: {
        payload: { from_adventure: number; user_id: number };
        addedIndex: null | number;
        removedIndex: null | number;
      },
      toAdventure: number
    ) {
      if (dropResult.addedIndex === null) {
        // Ignore this event. We'll get one targetting the actual destination contianer.
        return;
      }
      this.$emit('startAdminAction');
      try {
        await this.$api.patch('/api/player-assignments', {
          player_id: dropResult.payload.user_id,
          from_adventure_id: dropResult.payload.from_adventure,
          to_adventure_id: toAdventure,
        });
      } finally {
        this.$emit('finishAdminAction');
      }
      this.fetch(false);
    }
  },
  computed: {
    isDutchEvent(): boolean {
      return this.isDutchEventTitle(this.eventTypeTitle || '');
    },
    showWeekNavigation(): boolean {
      if (this.selectedEventType && typeof this.selectedEventType.is_single_event === 'boolean') {
        return !this.selectedEventType.is_single_event;
      }
      return true;
    },
    canGoEarlier(): boolean {
      if (this.me && this.me.privilege_level >= 1) {
        return true;
      }
      const today = new Date();
      const monday = new Date(today);
      monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
      const currentWeekStart = toLocalDateString(monday);
      return this.weekStart > currentWeekStart;
    },
    labels() {
      if (this.isDutchEvent) {
        return {
          earlier: 'Eerder',
          later: 'Later',
          loading: 'Laden...',
          assignmentNotice:
            'Sta browsernotificaties toe om toewijzingen direct te ontvangen. Heb je nog geen melding? Kijk later nog eens terug. Kun je toch niet komen, annuleer dan je plek zodat iemand van de wachtlijst kan doorschuiven.',
          noSessions: 'Nog geen sessies deze week. Maak er een!',
          noDescription: 'Geen beschrijving',
          noPlayersAssigned: 'Nog geen spelers toegewezen',
          oneShot: 'One-shot',
          moreDetails: 'Meer details',
          makeAdventure: 'Nieuw avontuur maken',
          duration: 'Duur',
          maxPlayers: 'Max spelers',
          signupsNotFinal: 'Inschrijvingen (geen definitieve indeling):',
          cancelSignup: 'Inschrijving annuleren',
          signUp: 'Inschrijven',
          signupSubmitted: 'Je inschrijving is verstuurd!',
          cancelAssignmentTitle: 'Toewijzing annuleren',
          cancelAssignmentMessage:
            'Weet je zeker dat je je plek op dit avontuur wilt opgeven? Je kunt deze plek niet terugkrijgen en de plek wordt aan iemand anders toegewezen. Gebruik dit alleen in noodgevallen.',
          cancelledAssignment: 'Je bent uitgeschreven!',
          choices: {
            1: 'Eerste keuze',
            2: 'Tweede keuze',
            3: 'Derde keuze',
          },
        };
      }
      return {
        earlier: 'Earlier',
        later: 'Later',
        loading: 'Loading...',
        assignmentNotice:
          'Allow browser notifications to receive assignment updates immediately. If you do not see an update yet, check back later. If you can no longer attend, cancel your assignment so someone from the waiting list can take your spot.',
        noSessions: 'No sessions this week yet. Make one!',
        noDescription: 'No description',
        noPlayersAssigned: 'No players assigned yet',
        oneShot: 'One shot',
        moreDetails: 'More details',
        makeAdventure: 'Make a new Adventure',
        duration: 'Duration',
        maxPlayers: 'Max players',
        signupsNotFinal: 'Signups (Not final assignments):',
        cancelSignup: 'Cancel signup',
        signUp: 'Sign up',
        signupSubmitted: 'Your signup is submitted!',
        cancelAssignmentTitle: 'Cancel Assignment',
        cancelAssignmentMessage:
          'Are you sure you want to give up your place on this adventure? You will not be able to reclaim it and the place will be assigned to someone else. Please note that this option is only for emergency',
        cancelledAssignment: "And you're off!",
        choices: {
          1: 'First choice',
          2: 'Second choice',
          3: 'Third choice',
        },
      };
    },
    choiceLabels() {
      return this.labels.choices;
    },
    displayDateLabel() {
      if (/^\d{4}-\d{2}-\d{2}$/.test(this.selectedDate)) {
        if (this.isDutchEvent) {
          return this.formatDutchDate(this.selectedDate);
        }
        return this.formatEnglishDate(this.selectedDate);
      }
      return this.isDutchEvent ? `Week van ${this.weekStart}` : `Week of ${this.weekStart}`;
    },
    weekEnd() {
      const d = fromDateString(this.weekStart);
      d.setDate(d.getDate() + 6);
      return toLocalDateString(d);
    },
  },
  watch: {
    '$route.query.date': {
      handler(date: string | undefined) {
        if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
          return;
        }
        this.selectedDate = date;
        const baseDate = fromDateString(date);
        const monday = new Date(baseDate);
        monday.setDate(baseDate.getDate() - ((baseDate.getDay() + 6) % 7));
        this.weekStart = toLocalDateString(monday);
      },
      immediate: true,
    },
    weekStart: {
      async handler() {
        await this.fetch(false);
      },
      immediate: true,
    },
    forceRefresh() {
      this.fetch(true);
    },
    eventTypeId() {
      this.fetch(true);
      this.fetchEventTypeMeta();
    },
  },
  async mounted() {
    await this.fetchEventTypeMeta();
  },
});
</script>
