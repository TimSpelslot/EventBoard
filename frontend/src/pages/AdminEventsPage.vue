<template>
  <q-page class="q-pa-lg admin-events-page">
    <div class="row items-center justify-between q-mb-lg">
      <div>
        <div class="text-h5">Event Operations</div>
        <div class="text-subtitle2 text-grey-7">
          Manage sessions, walk-ins, participants, and session notifications for the new event model.
        </div>
      </div>
      <div class="row q-gutter-sm">
        <q-btn v-if="canCreateEvents" color="secondary" icon="add" label="Create Event" @click="openEventDialog" />
        <q-btn color="primary" icon="refresh" label="Refresh" :loading="loading" @click="fetchEvents" />
      </div>
    </div>

    <q-banner v-if="!me" class="bg-warning text-black q-mb-lg" rounded>
      Login required.
    </q-banner>

    <q-banner v-else-if="!loading && manageableEvents.length === 0" class="bg-info text-white q-mb-lg" rounded>
      No manageable events found for your current permissions.
    </q-banner>

    <div v-if="loading" class="column items-center q-mt-xl">
      <q-spinner size="xl" />
      <div class="text-subtitle1 q-mt-md">Loading events...</div>
    </div>

    <div v-else class="column q-gutter-md">
      <q-expansion-item
        v-for="event in manageableEvents"
        :key="event.id"
        group="events"
        expand-separator
        :header-class="$q.dark.isActive ? 'event-header-dark' : 'event-header-light'"
        class="rounded-borders overflow-hidden"
      >
        <template #header>
          <q-item-section>
            <q-item-label class="text-subtitle1">{{ event.title }}</q-item-label>
            <q-item-label caption>
              {{ event.description || 'No description' }}
            </q-item-label>
          </q-item-section>
          <q-item-section side v-if="canAddDays(event)">
            <q-btn dense flat color="primary" icon="event_available" label="Add Day" @click.stop="openDayDialog(event)" />
          </q-item-section>
          <q-item-section side v-if="canCreateEvents">
            <q-btn dense flat color="grey" icon="edit" @click.stop="openEventEditDialog(event)" />
          </q-item-section>
          <q-item-section side>
            <q-chip dense color="primary" text-color="white">
              {{ event.days.length }} day{{ event.days.length === 1 ? '' : 's' }}
            </q-chip>
          </q-item-section>
        </template>

        <q-card flat bordered>
          <q-card-section class="column q-gutter-md">
            <div v-for="day in sortedDays(event.days)" :key="day.id" class="day-block">
              <div class="row items-center justify-between q-mb-sm">
                <div>
                  <div class="text-subtitle1">{{ formatDay(day) }}</div>
                  <div class="text-caption text-grey-7">{{ day.tables.length }} table{{ day.tables.length === 1 ? '' : 's' }}</div>
                </div>
                <div class="row q-gutter-sm">
                  <q-btn
                    v-if="canAddDays(event)"
                    dense
                    flat
                    color="secondary"
                    icon="edit_calendar"
                    label="Edit Day"
                    @click="openDayEditDialog(event, day)"
                  />
                  <q-btn
                    v-if="canAddTables(event)"
                    dense
                    flat
                    color="primary"
                    icon="table_restaurant"
                    label="Add Table"
                    @click="openTableDialog(event, day)"
                  />
                  <q-btn
                    v-if="canCreateSession(event)"
                    dense
                    flat
                    color="secondary"
                    icon="add_circle"
                    label="Add Session"
                    :disable="day.tables.length === 0"
                    @click="openSessionDialog(event, day)"
                  />
                </div>
              </div>

              <div v-if="day.tables.length > 0" class="row q-gutter-sm q-mb-md items-center">
                <q-chip
                  v-for="table in sortedTables(day.tables)"
                  :key="table.id"
                  :class="$q.dark.isActive ? 'table-chip-dark' : 'table-chip-light'"
                  class="q-pr-xs table-chip"
                >
                  <q-avatar v-if="table.image_url" rounded>
                    <img :src="table.image_url" alt="Table" />
                  </q-avatar>
                  <span>{{ table.name }}</span>
                  <span v-if="table.description" class="q-ml-xs text-caption">- {{ table.description }}</span>
                  <q-btn
                    v-if="canAddTables(event)"
                    dense
                    flat
                    round
                    size="sm"
                    icon="edit"
                    @click.stop="openTableEditDialog(event, day, table)"
                  />
                </q-chip>
              </div>

              <div class="row q-col-gutter-md">
                <div
                  v-for="session in sortedSessions(day.sessions)"
                  :key="session.id"
                  class="col-12 col-lg-6"
                >
                  <q-card class="session-card" flat bordered>
                    <q-card-section>
                      <div class="row items-start justify-between q-col-gutter-sm">
                        <div class="col">
                          <div class="text-subtitle1">{{ session.title }}</div>
                          <div class="text-caption text-grey-7 q-mt-xs">
                            {{ formatSessionMeta(session, day) }}
                          </div>
                          <div v-if="session.short_description" class="text-body2 q-mt-sm">{{ session.short_description }}</div>
                          <div v-if="session.gamemaster_name" class="text-caption q-mt-xs">Gamemaster: {{ session.gamemaster_name }}</div>
                        </div>
                        <div class="column q-gutter-xs session-actions">
                          <q-btn dense color="primary" icon="group" label="Participants" @click="openParticipants(session, event, day)" />
                          <q-btn dense outline color="secondary" icon="edit" label="Edit" @click="openSessionEditDialog(event, day, session)" />
                          <q-btn dense outline color="secondary" icon="person_add" label="Add Walk-in" @click="openGuestDialog(session, event, day)" />
                          <q-btn
                            v-if="event.placement_mode === 'delayed' && canManageSessions(event)"
                            dense
                            outline
                            color="positive"
                            icon="playlist_add_check"
                            label="Process Placements"
                            @click="processPlacements(session)"
                          />
                          <q-btn
                            dense
                            outline
                            color="accent"
                            icon="campaign"
                            label="Notify"
                            :disable="!canSendNotifications(event)"
                            @click="openNotifyDialog(session, event)"
                          />
                        </div>
                      </div>
                    </q-card-section>
                  </q-card>
                </div>
              </div>
            </div>
          </q-card-section>

          <q-separator v-if="canCreateEvents" />
          <q-card-section v-if="canCreateEvents" class="q-pt-sm">
            <div class="row items-center justify-between q-mb-sm">
              <div class="text-subtitle2 text-grey-7">Members ({{ event.memberships.length }})</div>
              <q-btn dense flat color="primary" icon="person_add" label="Add Member" @click="openMembershipDialog(event)" />
            </div>
            <div class="text-caption text-grey-7 q-mb-sm">
              Set per-event permissions here (Event Admin or Event Helper). Global privilege levels are managed in Approve users.
            </div>
            <div v-if="event.memberships.length > 0" class="row q-gutter-xs">
              <q-chip
                v-for="m in event.memberships"
                :key="m.user_id"
                :color="m.role === 'event_admin' ? 'secondary' : 'grey-4'"
                :text-color="m.role === 'event_admin' ? 'white' : 'black'"
                removable
                @remove="removeMembership(event, m)"
              >
                {{ m.user?.display_name || m.user_id }}&nbsp;
                <span class="text-caption">({{ m.role === 'event_admin' ? 'Admin' : 'Helper' }})</span>
              </q-chip>
            </div>
            <div v-else class="text-caption text-grey-6">No members yet.</div>
          </q-card-section>
        </q-card>
      </q-expansion-item>
    </div>

    <q-dialog v-model="participantsDialog.open" maximized>
      <q-card>
        <q-card-section class="row items-center justify-between">
          <div>
            <div class="text-h6">{{ participantsDialog.session?.title }}</div>
            <div class="text-subtitle2 text-grey-7">{{ participantsDialog.dayLabel }}</div>
          </div>
          <div class="row q-gutter-sm">
            <q-btn outline color="primary" icon="refresh" label="Refresh" :loading="participantsDialog.loading" @click="refreshParticipants" />
            <q-btn color="secondary" icon="person_add" label="Add Walk-in" @click="openGuestDialog(participantsDialog.session, participantsDialog.event, participantsDialog.day)" />
            <q-btn
              color="accent"
              icon="campaign"
              label="Notify"
              :disable="!canSendNotifications(participantsDialog.event)"
              @click="openNotifyDialog(participantsDialog.session, participantsDialog.event)"
            />
            <q-btn flat round icon="close" v-close-popup />
          </div>
        </q-card-section>

        <q-separator />

        <q-card-section>
          <div class="row q-col-gutter-sm q-mb-md">
            <div class="col-auto">
              <q-chip color="positive" text-color="white">Placed {{ statusCount('placed') }}</q-chip>
            </div>
            <div class="col-auto">
              <q-chip color="warning" text-color="black">Waitlist {{ statusCount('waitlist') }}</q-chip>
            </div>
            <div class="col-auto">
              <q-btn color="primary" icon="arrow_upward" label="Promote Next" :loading="participantsDialog.promoting" @click="promoteNext" />
            </div>
          </div>

          <q-table
            flat
            bordered
            row-key="id"
            :rows="participantsDialog.participants"
            :columns="participantColumns"
            :loading="participantsDialog.loading"
            :pagination="{ rowsPerPage: 50 }"
          >
            <template #body-cell-name="props">
              <q-td :props="props">
                <div class="text-body2">{{ participantName(props.row) }}</div>
                <div class="text-caption text-grey-7">{{ props.row.user_id ? 'Signed-in user' : 'Guest' }}</div>
              </q-td>
            </template>

            <template #body-cell-status="props">
              <q-td :props="props">
                <q-select
                  dense
                  outlined
                  emit-value
                  map-options
                  :options="participantStatusOptions"
                  :model-value="props.row.status"
                  @update:model-value="(value) => updateParticipantStatus(props.row, String(value))"
                />
              </q-td>
            </template>

            <template #body-cell-comment="props">
              <q-td :props="props">
                <div class="text-body2">{{ props.row.comment || '—' }}</div>
              </q-td>
            </template>

            <template #body-cell-actions="props">
              <q-td :props="props">
                <div class="row q-gutter-sm">
                  <q-btn
                    v-if="props.row.user_id"
                    dense
                    flat
                    color="accent"
                    icon="campaign"
                    @click="openParticipantNotifyDialog(props.row)"
                  />
                  <q-btn dense flat color="negative" icon="delete" @click="removeParticipant(props.row)" />
                </div>
              </q-td>
            </template>
          </q-table>
        </q-card-section>
      </q-card>
    </q-dialog>

    <q-dialog v-model="guestDialog.open">
      <q-card style="min-width: 420px">
        <q-card-section class="text-h6">Add Walk-in Player</q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input v-model="guestDialog.form.display_name" label="Player name" autofocus />
          <q-select
            v-model="guestDialog.form.status"
            :options="participantStatusOptions"
            emit-value
            map-options
            label="Initial status"
          />
          <q-input v-model="guestDialog.form.comment" label="Comment" type="textarea" autogrow />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" label="Add" :loading="guestDialog.saving" @click="submitGuest" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="notifyDialog.open">
      <q-card style="min-width: 460px">
        <q-card-section class="text-h6">Notify Session Participants</q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input v-model="notifyDialog.form.title" label="Title" />
          <q-input v-model="notifyDialog.form.body" label="Message" type="textarea" autogrow />
          <q-toggle v-model="notifyDialog.form.include_waitlist" label="Include waiting list" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="accent" label="Send" :loading="notifyDialog.saving" @click="submitNotify" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="participantNotifyDialog.open">
      <q-card style="min-width: 460px">
        <q-card-section class="text-h6">Notify Participant</q-card-section>
        <q-card-section class="q-gutter-md">
          <div class="text-caption text-grey-7">Recipient: {{ participantNotifyDialog.recipientName || 'Unknown user' }}</div>
          <q-input v-model="participantNotifyDialog.form.title" label="Title" />
          <q-input v-model="participantNotifyDialog.form.body" label="Message" type="textarea" autogrow />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="accent" label="Send" :loading="participantNotifyDialog.saving" @click="submitParticipantNotify" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Membership dialog -->
    <q-dialog v-model="membershipDialog.open">
      <q-card style="min-width: 420px">
        <q-card-section class="text-h6">Add Member</q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input
            v-model="membershipDialog.searchQuery"
            label="Search user by name"
            debounce="300"
            @update:model-value="searchMembershipUsers"
          />
          <q-list v-if="membershipDialog.searchResults.length > 0" bordered separator>
            <q-item
              v-for="user in membershipDialog.searchResults"
              :key="user.id"
              clickable
              @click="membershipDialog.form.user_id = user.id; membershipDialog.selectedUserName = user.display_name"
              :class="{ 'bg-blue-1': membershipDialog.form.user_id === user.id }"
            >
              <q-item-section>{{ user.display_name }}</q-item-section>
              <q-item-section side v-if="membershipDialog.form.user_id === user.id">
                <q-icon name="check" color="primary" />
              </q-item-section>
            </q-item>
          </q-list>
          <div v-if="membershipDialog.form.user_id" class="text-caption text-grey-7">
            Selected: {{ membershipDialog.selectedUserName }}
          </div>
          <q-select
            v-model="membershipDialog.form.role"
            :options="[{ label: 'Event Admin', value: 'event_admin' }, { label: 'Event Helper', value: 'event_helper' }]"
            emit-value map-options label="Role"
          />
          <q-toggle v-model="membershipDialog.form.can_send_notifications" label="Can send notifications" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" label="Add" :loading="membershipDialog.saving" :disable="!membershipDialog.form.user_id" @click="submitMembership" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="eventDialog.open">
      <q-card style="min-width: 460px">
        <q-card-section class="text-h6">{{ eventDialog.editingEventId ? 'Edit Event' : 'Create Event' }}</q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input v-model="eventDialog.form.title" label="Title" autofocus />
          <q-input v-model="eventDialog.form.description" label="Description" type="textarea" autogrow />
          <q-input v-model="eventDialog.form.image_url" label="Event image URL (optional)" />
          <q-select
            v-model="eventDialog.form.notification_days_before"
            :options="notificationLeadOptions"
            emit-value
            map-options
            label="Reminder lead time"
          />
          <q-select
            v-model="eventDialog.form.placement_mode"
            :options="placementModeOptions"
            emit-value
            map-options
            label="Placement mode"
          />
          <q-toggle v-model="eventDialog.form.release_assignments" label="Assignments released immediately" />
          <q-toggle v-model="eventDialog.form.allow_event_admin_notifications" label="Allow event-admin notifications" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn
            v-if="eventDialog.editingEventId"
            flat
            color="negative"
            label="Delete"
            :loading="eventDialog.deleting"
            @click="deleteEvent"
          />
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="secondary" :label="eventDialog.editingEventId ? 'Save' : 'Create'" :loading="eventDialog.saving" @click="submitEvent" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="dayDialog.open">
      <q-card style="min-width: 420px">
        <q-card-section class="text-h6">{{ dayDialog.editingDayId ? 'Edit Event Day' : 'Add Event Day' }}</q-card-section>
        <q-card-section class="q-gutter-md">
          <DatePicker v-model="dayDialog.form.date" label="Date" />
          <q-input v-model="dayDialog.form.label" label="Label" hint="Optional, e.g. Day 1 or Saturday" />
          <q-input v-model.number="dayDialog.form.sort_order" type="number" label="Sort order" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn
            v-if="dayDialog.editingDayId"
            flat
            color="negative"
            label="Delete"
            :loading="dayDialog.deleting"
            @click="deleteDay"
          />
          <q-space />
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" :label="dayDialog.editingDayId ? 'Save Day' : 'Add Day'" :loading="dayDialog.saving" @click="submitDay" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="tableDialog.open">
      <q-card style="min-width: 420px">
        <q-card-section class="text-h6">{{ tableDialog.editingTableId ? 'Edit Table' : 'Add Table' }}</q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input v-model="tableDialog.form.name" label="Table name" autofocus />
          <q-input v-model="tableDialog.form.description" label="Table description (optional)" type="textarea" autogrow />
          <q-input v-model="tableDialog.form.image_url" label="Table image URL (optional)" />
          <q-input v-model.number="tableDialog.form.sort_order" type="number" label="Sort order" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn
            v-if="tableDialog.editingTableId"
            flat
            color="negative"
            label="Delete"
            :loading="tableDialog.deleting"
            @click="deleteTable"
          />
          <q-space />
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" :label="tableDialog.editingTableId ? 'Save Table' : 'Add Table'" :loading="tableDialog.saving" @click="submitTable" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <q-dialog v-model="sessionDialog.open">
      <q-card style="min-width: 520px">
        <q-card-section class="text-h6">{{ sessionDialog.editingSessionId ? 'Edit Session' : 'Add Session' }}</q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input v-model="sessionDialog.form.title" label="Title" autofocus />
          <q-input v-model="sessionDialog.form.short_description" label="Description (optional)" type="textarea" autogrow />
          <q-select
            v-model="sessionDialog.form.event_table_id"
            :options="sessionDialog.tableOptions"
            emit-value
            map-options
            label="Table"
          />
          <div class="row q-col-gutter-md">
            <div class="col-4">
              <q-input v-model="sessionDialog.form.start_time" label="Start time" mask="##:##" hint="24h" />
            </div>
            <div class="col-4">
              <q-input v-model.number="sessionDialog.form.duration_minutes" type="number" label="Duration (minutes)" />
            </div>
            <div class="col-4">
              <q-input v-model.number="sessionDialog.form.max_players" type="number" label="Capacity" />
            </div>
          </div>
          <q-input v-model="sessionDialog.form.gamemaster_name" label="Gamemaster (optional)" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn
            v-if="sessionDialog.editingSessionId"
            flat
            color="negative"
            label="Delete"
            :loading="sessionDialog.deleting"
            @click="deleteSession"
          />
          <q-space />
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="secondary" :label="sessionDialog.editingSessionId ? 'Save Session' : 'Add Session'" :loading="sessionDialog.saving" @click="submitSession" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script lang="ts">
import { defineComponent, inject } from 'vue';
import DatePicker from 'src/components/DatePicker.vue';

type EventMembership = {
  id: number;
  user_id: number;
  role: string;
  can_send_notifications: boolean;
  user?: { id: number; display_name: string };
};

type EventTable = {
  id: number;
  name: string;
  description?: string | null;
  image_url?: string | null;
};

type EventSession = {
  id: number;
  title: string;
  short_description?: string | null;
  gamemaster_name?: string | null;
  event_table_id: number;
  host_user_id: number | null;
  max_players: number;
  start_time: string;
  duration_minutes: number;
  placement_mode: string;
};

type EventDay = {
  id: number;
  date: string;
  label?: string | null;
  tables: EventTable[];
  sessions: EventSession[];
};

type ManagedEvent = {
  id: number;
  title: string;
  description?: string | null;
  image_url?: string | null;
  notification_days_before: number;
  placement_mode: string;
  release_assignments: boolean;
  allow_event_admin_notifications: boolean;
  memberships: EventMembership[];
  days: EventDay[];
};

type Participant = {
  id: number;
  user_id: number | null;
  guest_player_id: number | null;
  status: string;
  comment?: string | null;
  user?: { id: number; display_name: string };
  guest_player?: { id: number; display_name: string };
};

export default defineComponent({
  name: 'AdminEventsPage',
  components: { DatePicker },
  emits: ['mustLogin'],
  setup() {
    return {
      me: inject('me') as any,
      notificationLeadOptions: [
        { label: '1 day', value: 1 },
        { label: '2 days', value: 2 },
        { label: '3 days', value: 3 },
        { label: '7 days', value: 7 },
      ],
      placementModeOptions: [
        { label: 'Delayed', value: 'delayed' },
        { label: 'Immediate', value: 'immediate' },
      ],
      participantStatusOptions: [
        { label: 'Placed', value: 'placed' },
        { label: 'Waitlist', value: 'waitlist' },
        { label: 'Cancelled', value: 'cancelled' },
      ],
      participantColumns: [
        { name: 'name', label: 'Participant', field: 'name', align: 'left' as const },
        { name: 'status', label: 'Status', field: 'status', align: 'left' as const },
        { name: 'comment', label: 'Comment', field: 'comment', align: 'left' as const },
        { name: 'actions', label: 'Actions', field: 'actions', align: 'left' as const },
      ],
    };
  },
  data() {
    return {
      loading: false,
      events: [] as ManagedEvent[],
      participantsDialog: {
        open: false,
        loading: false,
        promoting: false,
        participants: [] as Participant[],
        session: null as EventSession | null,
        event: null as ManagedEvent | null,
        day: null as EventDay | null,
        dayLabel: '',
      },
      guestDialog: {
        open: false,
        saving: false,
        session: null as EventSession | null,
        form: {
          display_name: '',
          status: 'placed',
          comment: '',
        },
      },
      notifyDialog: {
        open: false,
        saving: false,
        session: null as EventSession | null,
        event: null as ManagedEvent | null,
        form: {
          title: '',
          body: '',
          include_waitlist: true,
        },
      },
      participantNotifyDialog: {
        open: false,
        saving: false,
        participant: null as Participant | null,
        recipientName: '',
        form: {
          title: '',
          body: '',
        },
      },
      eventDialog: {
        open: false,
        saving: false,
        deleting: false,
        editingEventId: null as number | null,
        form: {
          title: '',
          description: '',
          image_url: '',
          notification_days_before: 2,
          placement_mode: 'delayed',
          release_assignments: false,
          allow_event_admin_notifications: false,
        },
      },
      dayDialog: {
        open: false,
        saving: false,
        deleting: false,
        editingDayId: null as number | null,
        event: null as ManagedEvent | null,
        form: {
          date: '',
          label: '',
          sort_order: 0,
        },
      },
      tableDialog: {
        open: false,
        saving: false,
        deleting: false,
        editingTableId: null as number | null,
        event: null as ManagedEvent | null,
        day: null as EventDay | null,
        form: {
          name: '',
          description: '',
          image_url: '',
          sort_order: 0,
        },
      },
      sessionDialog: {
        open: false,
        saving: false,
        deleting: false,
        editingSessionId: null as number | null,
        event: null as ManagedEvent | null,
        day: null as EventDay | null,
        tableOptions: [] as Array<{ label: string; value: number }>,
        form: {
          title: '',
          short_description: '',
          gamemaster_name: '',
          event_table_id: null as number | null,
          start_time: '',
          duration_minutes: 60,
          max_players: 5,
        },
      },
      membershipDialog: {
        open: false,
        saving: false,
        event: null as ManagedEvent | null,
        searchQuery: '',
        searchResults: [] as Array<{ id: number; display_name: string }>,
        selectedUserName: '',
        form: {
          user_id: null as number | null,
          role: 'event_helper',
          can_send_notifications: false,
        },
      },
    };
  },
  computed: {
    canCreateEvents(): boolean {
      return !!this.me && this.me.privilege_level >= 2;
    },
    manageableEvents(): ManagedEvent[] {
      if (!this.me) {
        return [];
      }

      return this.events.filter((event) => this.canManageSessions(event));
    },
  },
  async mounted() {
    if (!this.me) {
      this.$emit('mustLogin');
      return;
    }
    await this.fetchEvents();
  },
  methods: {
    async fetchEvents() {
      this.loading = true;
      try {
        const response = await this.$api.get('/api/events');
        this.events = response.data || [];
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to fetch events' });
      } finally {
        this.loading = false;
      }
    },
    sortedDays(days: EventDay[]) {
      return [...(days || [])].sort((a, b) => String(a.date).localeCompare(String(b.date)));
    },
    sortedSessions(sessions: EventSession[]) {
      return [...(sessions || [])].sort((a, b) => String(a.start_time).localeCompare(String(b.start_time)));
    },
    sortedTables(tables: EventTable[]) {
      return [...(tables || [])].sort((a, b) => String(a.name).localeCompare(String(b.name)));
    },
    membershipFor(event: ManagedEvent) {
      return (event.memberships || []).find((membership) => membership.user_id === this.me?.id) || null;
    },
    canManageSessions(event: ManagedEvent) {
      if (!this.me) {
        return false;
      }
      if (this.me.privilege_level >= 2) {
        return true;
      }
      const membership = this.membershipFor(event);
      return !!membership && ['event_admin', 'event_helper'].includes(membership.role);
    },
    canAddDays(event: ManagedEvent) {
      return !!this.me && this.me.privilege_level >= 2;
    },
    canAddTables(event: ManagedEvent) {
      if (!this.me) {
        return false;
      }
      if (this.me.privilege_level >= 2) {
        return true;
      }
      const membership = this.membershipFor(event);
      return !!membership && membership.role === 'event_admin';
    },
    canCreateSession(event: ManagedEvent) {
      return this.canManageSessions(event);
    },
    canSendNotifications(event: ManagedEvent | null) {
      if (!event || !this.me) {
        return false;
      }
      if (this.me.privilege_level >= 2) {
        return true;
      }
      const membership = this.membershipFor(event);
      return !!membership && membership.role === 'event_admin' && event.allow_event_admin_notifications && membership.can_send_notifications;
    },
    openEventDialog() {
      this.eventDialog.open = true;
      this.eventDialog.editingEventId = null;
      this.eventDialog.form = {
        title: '',
        description: '',
        image_url: '',
        notification_days_before: 2,
        placement_mode: 'delayed',
        release_assignments: false,
        allow_event_admin_notifications: false,
      };
    },
    openEventEditDialog(event: ManagedEvent) {
      this.eventDialog.open = true;
      this.eventDialog.editingEventId = event.id;
      this.eventDialog.form = {
        title: event.title,
        description: event.description || '',
        image_url: event.image_url || '',
        notification_days_before: event.notification_days_before ?? 2,
        placement_mode: event.placement_mode ?? 'delayed',
        release_assignments: event.release_assignments ?? false,
        allow_event_admin_notifications: event.allow_event_admin_notifications ?? false,
      };
    },
    async submitEvent() {
      if (!this.eventDialog.form.title.trim()) {
        return;
      }
      this.eventDialog.saving = true;
      try {
        const payload = {
          title: this.eventDialog.form.title.trim(),
          description: this.eventDialog.form.description || null,
          image_url: this.eventDialog.form.image_url || null,
          notification_days_before: this.eventDialog.form.notification_days_before,
          placement_mode: this.eventDialog.form.placement_mode,
          release_assignments: this.eventDialog.form.release_assignments,
          allow_event_admin_notifications: this.eventDialog.form.allow_event_admin_notifications,
        };
        if (this.eventDialog.editingEventId) {
          await this.$api.patch(`/api/events/${this.eventDialog.editingEventId}`, payload);
          this.$q.notify({ type: 'positive', message: 'Event updated' });
        } else {
          await this.$api.post('/api/events', payload);
          this.$q.notify({ type: 'positive', message: 'Event created' });
        }
        this.eventDialog.open = false;
        await this.fetchEvents();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || `Failed to ${this.eventDialog.editingEventId ? 'update' : 'create'} event` });
      } finally {
        this.eventDialog.saving = false;
      }
    },
    async deleteEvent() {
      if (!this.eventDialog.editingEventId) {
        return;
      }
      this.eventDialog.deleting = true;
      try {
        await this.$api.delete(`/api/events/${this.eventDialog.editingEventId}`);
        this.$q.notify({ type: 'positive', message: 'Event deleted' });
        this.eventDialog.open = false;
        await this.fetchEvents();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to delete event' });
      } finally {
        this.eventDialog.deleting = false;
      }
    },
    async processPlacements(session: EventSession) {
      try {
        const response = await this.$api.post(`/api/event-sessions/${session.id}/process-placements`);
        this.$q.notify({ type: 'positive', message: response.data?.message || 'Placements processed' });
        await this.fetchEvents();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to process placements' });
      }
    },
    openMembershipDialog(event: ManagedEvent) {
      this.membershipDialog.open = true;
      this.membershipDialog.event = event;
      this.membershipDialog.searchQuery = '';
      this.membershipDialog.searchResults = [];
      this.membershipDialog.selectedUserName = '';
      this.membershipDialog.form = { user_id: null, role: 'event_helper', can_send_notifications: false };
    },
    async searchMembershipUsers(q: string) {
      if (!this.membershipDialog.event || !q.trim()) {
        this.membershipDialog.searchResults = [];
        return;
      }
      // Reuse eligible-users from any session of the event, or fall back to a generic user search
      // We'll search all users via the eligible-users endpoint of an arbitrary session, if available,
      // or just get all users matching the query
      try {
        // Find any session to borrow the eligible-users search endpoint
        let sessionId: number | null = null;
        for (const day of (this.membershipDialog.event.days || [])) {
          for (const s of (day.sessions || [])) {
            sessionId = s.id;
            break;
          }
          if (sessionId) break;
        }
        if (sessionId) {
          const res = await this.$api.get(`/api/event-sessions/${sessionId}/eligible-users?q=${encodeURIComponent(q)}`);
          this.membershipDialog.searchResults = res.data || [];
        } else {
          // No sessions yet — search via users endpoint (super-admin only)
          const res = await this.$api.get(`/api/users?q=${encodeURIComponent(q)}`);
          this.membershipDialog.searchResults = (res.data || []).slice(0, 10);
        }
      } catch {
        this.membershipDialog.searchResults = [];
      }
    },
    async submitMembership() {
      if (!this.membershipDialog.event || !this.membershipDialog.form.user_id) {
        return;
      }
      this.membershipDialog.saving = true;
      try {
        await this.$api.post(`/api/events/${this.membershipDialog.event.id}/memberships`, {
          user_id: this.membershipDialog.form.user_id,
          role: this.membershipDialog.form.role,
          can_send_notifications: this.membershipDialog.form.can_send_notifications,
        });
        this.$q.notify({ type: 'positive', message: 'Member added' });
        this.membershipDialog.open = false;
        await this.fetchEvents();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to add member' });
      } finally {
        this.membershipDialog.saving = false;
      }
    },
    async removeMembership(event: ManagedEvent, membership: EventMembership) {
      this.$q.dialog({
        title: 'Remove member',
        message: `Remove ${membership.user?.display_name || 'this member'} from the event?`,
        cancel: true,
        persistent: true,
      }).onOk(async () => {
        try {
          await this.$api.delete(`/api/events/${event.id}/memberships/${membership.id}`);
          this.$q.notify({ type: 'positive', message: 'Member removed' });
          await this.fetchEvents();
        } catch (error) {
          this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to remove member' });
        }
      });
    },
    openDayDialog(event: ManagedEvent) {
      this.dayDialog.open = true;
      this.dayDialog.editingDayId = null;
      this.dayDialog.event = event;
      this.dayDialog.form = {
        date: '',
        label: '',
        sort_order: (event.days || []).length,
      };
    },
    openDayEditDialog(event: ManagedEvent, day: EventDay) {
      this.dayDialog.open = true;
      this.dayDialog.editingDayId = day.id;
      this.dayDialog.event = event;
      this.dayDialog.form = {
        date: day.date,
        label: day.label || '',
        sort_order: (day as EventDay & { sort_order?: number }).sort_order || 0,
      };
    },
    async submitDay() {
      if (!this.dayDialog.event || !this.dayDialog.form.date) {
        return;
      }
      this.dayDialog.saving = true;
      try {
        const payload = {
          date: this.dayDialog.form.date,
          label: this.dayDialog.form.label || null,
          sort_order: this.dayDialog.form.sort_order,
        };
        if (this.dayDialog.editingDayId) {
          await this.$api.patch(`/api/event-days/${this.dayDialog.editingDayId}`, payload);
          this.$q.notify({ type: 'positive', message: 'Event day updated' });
        } else {
          await this.$api.post(`/api/events/${this.dayDialog.event.id}/days`, payload);
          this.$q.notify({ type: 'positive', message: 'Event day added' });
        }
        this.dayDialog.open = false;
        await this.fetchEvents();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || `Failed to ${this.dayDialog.editingDayId ? 'update' : 'add'} event day` });
      } finally {
        this.dayDialog.saving = false;
      }
    },
    async deleteDay() {
      if (!this.dayDialog.editingDayId) {
        return;
      }
      this.dayDialog.deleting = true;
      try {
        await this.$api.delete(`/api/event-days/${this.dayDialog.editingDayId}`);
        this.$q.notify({ type: 'positive', message: 'Event day deleted' });
        this.dayDialog.open = false;
        await this.fetchEvents();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to delete event day' });
      } finally {
        this.dayDialog.deleting = false;
      }
    },
    openTableDialog(event: ManagedEvent, day: EventDay) {
      this.tableDialog.open = true;
      this.tableDialog.editingTableId = null;
      this.tableDialog.event = event;
      this.tableDialog.day = day;
      this.tableDialog.form = {
        name: '',
        description: '',
        image_url: '',
        sort_order: (day.tables || []).length,
      };
    },
    openTableEditDialog(event: ManagedEvent, day: EventDay, table: EventTable) {
      this.tableDialog.open = true;
      this.tableDialog.editingTableId = table.id;
      this.tableDialog.event = event;
      this.tableDialog.day = day;
      this.tableDialog.form = {
        name: table.name,
        description: table.description || '',
        image_url: table.image_url || '',
        sort_order: (table as EventTable & { sort_order?: number }).sort_order || 0,
      };
    },
    async submitTable() {
      if (!this.tableDialog.day || !this.tableDialog.form.name.trim()) {
        return;
      }
      this.tableDialog.saving = true;
      try {
        const payload = {
          name: this.tableDialog.form.name.trim(),
          description: this.tableDialog.form.description || null,
          image_url: this.tableDialog.form.image_url || null,
          sort_order: this.tableDialog.form.sort_order,
        };
        if (this.tableDialog.editingTableId) {
          await this.$api.patch(`/api/event-tables/${this.tableDialog.editingTableId}`, payload);
          this.$q.notify({ type: 'positive', message: 'Table updated' });
        } else {
          await this.$api.post(`/api/event-days/${this.tableDialog.day.id}/tables`, payload);
          this.$q.notify({ type: 'positive', message: 'Table added' });
        }
        this.tableDialog.open = false;
        await this.fetchEvents();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || `Failed to ${this.tableDialog.editingTableId ? 'update' : 'add'} table` });
      } finally {
        this.tableDialog.saving = false;
      }
    },
    async deleteTable() {
      if (!this.tableDialog.editingTableId) {
        return;
      }
      this.tableDialog.deleting = true;
      try {
        await this.$api.delete(`/api/event-tables/${this.tableDialog.editingTableId}`);
        this.$q.notify({ type: 'positive', message: 'Table deleted' });
        this.tableDialog.open = false;
        await this.fetchEvents();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to delete table' });
      } finally {
        this.tableDialog.deleting = false;
      }
    },
    openSessionDialog(event: ManagedEvent, day: EventDay) {
      this.sessionDialog.open = true;
      this.sessionDialog.editingSessionId = null;
      this.sessionDialog.event = event;
      this.sessionDialog.day = day;
      this.sessionDialog.tableOptions = (day.tables || []).map((table) => ({ label: table.name, value: table.id }));
      this.sessionDialog.form = {
        title: '',
        short_description: '',
        gamemaster_name: '',
        event_table_id: day.tables[0]?.id ?? null,
        start_time: '',
        duration_minutes: 60,
        max_players: 5,
      };
    },
    openSessionEditDialog(event: ManagedEvent, day: EventDay, session: EventSession) {
      this.sessionDialog.open = true;
      this.sessionDialog.editingSessionId = session.id;
      this.sessionDialog.event = event;
      this.sessionDialog.day = day;
      this.sessionDialog.tableOptions = (day.tables || []).map((table) => ({ label: table.name, value: table.id }));
      this.sessionDialog.form = {
        title: session.title,
        short_description: session.short_description || '',
        gamemaster_name: session.gamemaster_name || '',
        event_table_id: session.event_table_id,
        start_time: session.start_time.slice(0, 5),
        duration_minutes: session.duration_minutes,
        max_players: session.max_players,
      };
    },
    async submitSession() {
      if (!this.sessionDialog.day || !this.sessionDialog.form.title.trim() || !this.sessionDialog.form.event_table_id || !this.sessionDialog.form.start_time) {
        return;
      }
      this.sessionDialog.saving = true;
      try {
        const payload = {
          title: this.sessionDialog.form.title.trim(),
          short_description: this.sessionDialog.form.short_description?.trim() || null,
          gamemaster_name: this.sessionDialog.form.gamemaster_name?.trim() || null,
          event_table_id: this.sessionDialog.form.event_table_id,
          start_time: this.sessionDialog.form.start_time,
          duration_minutes: this.sessionDialog.form.duration_minutes,
          max_players: this.sessionDialog.form.max_players,
        };
        if (this.sessionDialog.editingSessionId) {
          await this.$api.patch(`/api/event-sessions/${this.sessionDialog.editingSessionId}`, payload);
          this.$q.notify({ type: 'positive', message: 'Session updated' });
        } else {
          await this.$api.post(`/api/event-days/${this.sessionDialog.day.id}/sessions`, payload);
          this.$q.notify({ type: 'positive', message: 'Session added' });
        }
        this.sessionDialog.open = false;
        await this.fetchEvents();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || `Failed to ${this.sessionDialog.editingSessionId ? 'update' : 'add'} session` });
      } finally {
        this.sessionDialog.saving = false;
      }
    },
    async deleteSession() {
      if (!this.sessionDialog.editingSessionId) {
        return;
      }
      this.sessionDialog.deleting = true;
      try {
        await this.$api.delete(`/api/event-sessions/${this.sessionDialog.editingSessionId}`);
        this.$q.notify({ type: 'positive', message: 'Session deleted' });
        this.sessionDialog.open = false;
        await this.fetchEvents();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to delete session' });
      } finally {
        this.sessionDialog.deleting = false;
      }
    },
    formatDay(day: EventDay) {
      const date = new Date(day.date);
      const label = Number.isNaN(date.getTime()) ? day.date : date.toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' });
      return day.label ? `${day.label} · ${label}` : label;
    },
    tableName(day: EventDay, tableId: number) {
      return (day.tables || []).find((table) => table.id === tableId)?.name || `Table ${tableId}`;
    },
    formatSessionMeta(session: EventSession, day: EventDay) {
      return `${this.tableName(day, session.event_table_id)} · ${session.start_time.slice(0, 5)} · ${session.duration_minutes} min · cap ${session.max_players}`;
    },
    participantName(participant: Participant) {
      return participant.user?.display_name || participant.guest_player?.display_name || 'Unknown participant';
    },
    async openParticipants(session: EventSession | null, event: ManagedEvent | null, day: EventDay | null) {
      if (!session || !event || !day) {
        return;
      }
      this.participantsDialog.open = true;
      this.participantsDialog.session = session;
      this.participantsDialog.event = event;
      this.participantsDialog.day = day;
      this.participantsDialog.dayLabel = this.formatDay(day);
      await this.refreshParticipants();
    },
    async refreshParticipants() {
      if (!this.participantsDialog.session) {
        return;
      }
      this.participantsDialog.loading = true;
      try {
        const response = await this.$api.get(`/api/event-sessions/${this.participantsDialog.session.id}/participants`);
        this.participantsDialog.participants = response.data || [];
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to fetch participants' });
      } finally {
        this.participantsDialog.loading = false;
      }
    },
    statusCount(status: string) {
      return this.participantsDialog.participants.filter((participant) => participant.status === status).length;
    },
    openGuestDialog(session: EventSession | null, event: ManagedEvent | null, day: EventDay | null) {
      if (!session || !event || !day) {
        return;
      }
      this.guestDialog.open = true;
      this.guestDialog.session = session;
      this.guestDialog.form = {
        display_name: '',
        status: 'placed',
        comment: '',
      };
    },
    async submitGuest() {
      if (!this.guestDialog.session || !this.guestDialog.form.display_name.trim()) {
        return;
      }
      this.guestDialog.saving = true;
      try {
        await this.$api.post(`/api/event-sessions/${this.guestDialog.session.id}/participants/manual`, {
          display_name: this.guestDialog.form.display_name.trim(),
          status: this.guestDialog.form.status,
          comment: this.guestDialog.form.comment || null,
        });
        this.$q.notify({ type: 'positive', message: 'Walk-in added' });
        this.guestDialog.open = false;
        if (this.participantsDialog.open && this.participantsDialog.session?.id === this.guestDialog.session.id) {
          await this.refreshParticipants();
        }
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to add walk-in player' });
      } finally {
        this.guestDialog.saving = false;
      }
    },
    async updateParticipantStatus(participant: Participant, status: string) {
      try {
        await this.$api.patch(`/api/event-sessions/participants/${participant.id}`, { status });
        participant.status = status;
        await this.refreshParticipants();
        this.$q.notify({ type: 'positive', message: 'Participant updated' });
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to update participant' });
      }
    },
    async removeParticipant(participant: Participant) {
      try {
        await this.$api.delete(`/api/event-sessions/participants/${participant.id}`);
        this.$q.notify({ type: 'positive', message: 'Participant removed' });
        await this.refreshParticipants();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to remove participant' });
      }
    },
    async promoteNext() {
      if (!this.participantsDialog.session) {
        return;
      }
      this.participantsDialog.promoting = true;
      try {
        await this.$api.post(`/api/event-sessions/${this.participantsDialog.session.id}/participants/promote-next`);
        this.$q.notify({ type: 'positive', message: 'Next waitlist participant promoted' });
        await this.refreshParticipants();
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'No promotable waitlist participant available' });
      } finally {
        this.participantsDialog.promoting = false;
      }
    },
    openNotifyDialog(session: EventSession | null, event: ManagedEvent | null) {
      if (!session || !event || !this.canSendNotifications(event)) {
        return;
      }
      this.notifyDialog.open = true;
      this.notifyDialog.session = session;
      this.notifyDialog.event = event;
      this.notifyDialog.form = {
        title: `Update for ${session.title}`,
        body: '',
        include_waitlist: true,
      };
    },
    openParticipantNotifyDialog(participant: Participant) {
      if (!participant.user_id) {
        return;
      }
      this.participantNotifyDialog.open = true;
      this.participantNotifyDialog.participant = participant;
      this.participantNotifyDialog.recipientName = this.participantName(participant);
      this.participantNotifyDialog.form = {
        title: `Session update for ${this.participantName(participant)}`,
        body: '',
      };
    },
    async submitNotify() {
      if (!this.notifyDialog.session) {
        return;
      }
      this.notifyDialog.saving = true;
      try {
        const response = await this.$api.post(`/api/event-sessions/${this.notifyDialog.session.id}/notify`, this.notifyDialog.form);
        this.$q.notify({ type: 'positive', message: response.data?.message || 'Participants notified' });
        this.notifyDialog.open = false;
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to notify participants' });
      } finally {
        this.notifyDialog.saving = false;
      }
    },
    async submitParticipantNotify() {
      if (!this.participantNotifyDialog.participant?.id) {
        return;
      }
      this.participantNotifyDialog.saving = true;
      try {
        const response = await this.$api.post(
          `/api/event-sessions/participants/${this.participantNotifyDialog.participant.id}/notify`,
          this.participantNotifyDialog.form,
        );
        this.$q.notify({ type: 'positive', message: response.data?.message || 'Participant notified' });
        this.participantNotifyDialog.open = false;
      } catch (error) {
        this.$q.notify({ type: 'negative', message: this.$extractErrors(error).join(', ') || 'Failed to notify participant' });
      } finally {
        this.participantNotifyDialog.saving = false;
      }
    },
  },
});
</script>

<style scoped>
.admin-events-page {
  max-width: 1400px;
  margin: 0 auto;
}

.session-card {
  height: 100%;
}

.session-actions {
  min-width: 10rem;
}

.event-header-light {
  background: #f2f4f7;
}

.event-header-dark {
  background: #1f2a35;
  color: #f3f8fc;
}

.table-chip {
  border: 1px solid rgba(78, 96, 116, 0.2);
}

.table-chip-light {
  background: #e9edf2;
  color: #1f2933;
}

.table-chip-dark {
  background: rgba(34, 47, 61, 0.92);
  color: #eef6ff;
}

.day-block + .day-block {
  padding-top: 1rem;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}

:global(.body--dark) .day-block + .day-block {
  border-top: 1px solid rgba(184, 205, 225, 0.22);
}
</style>