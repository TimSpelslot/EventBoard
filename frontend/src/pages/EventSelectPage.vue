<template>
  <q-page class="q-pa-lg">
    <div class="row items-center justify-between q-mb-lg">
      <div class="text-h5">Choose Event</div>
      <div class="row q-gutter-sm" v-if="me?.privilege_level >= 2">
        <q-btn
          color="primary"
          icon="add"
          label="Create Event Type"
          @click="openCreateDialog"
        />
      </div>
    </div>

    <div v-if="loading" class="column items-center q-mt-xl">
      <q-spinner size="xl" />
    </div>

    <div v-else class="row q-col-gutter-md justify-center">
      <div
        v-for="eventType in eventTypes"
        :key="eventType.id"
        class="col-12 col-sm-6 col-lg-4 col-xl-3"
      >
        <q-card class="event-card cursor-pointer" @click="goToEvent(eventType)">
          <q-btn
            v-if="me?.privilege_level >= 2"
            class="edit-event-btn"
            color="accent"
            icon="edit"
            round
            dense
            @click.stop="openEditDialog(eventType)"
          />
          <div
            class="event-hero"
            :style="heroStyle(eventType.image_url)"
          >
            <div class="event-overlay">
              <div class="text-h6 text-white">{{ eventType.title }}</div>
              <div class="text-subtitle2 text-grey-3 q-mt-sm">
                {{ nextDateLabel(eventType) }}
              </div>
            </div>
          </div>
          <q-card-section>
            <div class="text-body1">{{ eventType.description || 'No description' }}</div>
          </q-card-section>
        </q-card>
      </div>
    </div>

    <q-dialog v-model="showDialog">
      <q-card style="min-width: 420px">
        <q-card-section class="text-h6">{{ dialogLabels.dialogTitle }}</q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input v-model="form.title" :label="dialogLabels.title" />
          <q-input v-model="form.description" :label="dialogLabels.description" type="textarea" autogrow />
          <q-input v-model="form.image_url" :label="dialogLabels.imageUrl" />
          <q-toggle v-model="form.is_single_event" :label="dialogLabels.singleEvent" />
          <DatePicker
            v-if="form.is_single_event"
            v-model="form.single_date"
            :label="dialogLabels.singleEventDate"
          />
          <q-select
            v-if="!form.is_single_event"
            v-model="form.week_of_month"
            :options="dialogWeekOptions"
            emit-value
            map-options
            :label="dialogLabels.weekOfMonth"
          />
          <q-select
            v-if="!form.is_single_event"
            v-model="form.weekday"
            :options="dialogWeekdayOptions"
            emit-value
            map-options
            :label="dialogLabels.weekday"
          />
          <q-toggle v-model="form.exclude_july_august" :label="dialogLabels.excludeJulyAugust" />
          <q-input v-model.number="form.sort_order" :label="dialogLabels.sortOrder" type="number" />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat :label="dialogLabels.cancel" v-close-popup />
          <q-btn color="primary" :label="dialogLabels.save" @click="saveEventType" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<script lang="ts">
import { defineComponent, inject } from 'vue';
import DatePicker from 'src/components/DatePicker.vue';

export default defineComponent({
  name: 'EventSelectPage',
  components: { DatePicker },
  setup() {
    return {
      me: inject('me') as any,
      weekdayOptions: [
        { label: 'Monday', value: 0 },
        { label: 'Tuesday', value: 1 },
        { label: 'Wednesday', value: 2 },
        { label: 'Thursday', value: 3 },
        { label: 'Friday', value: 4 },
        { label: 'Saturday', value: 5 },
        { label: 'Sunday', value: 6 },
      ],
      weekOptions: [
        { label: 'First', value: 1 },
        { label: 'Second', value: 2 },
        { label: 'Third', value: 3 },
        { label: 'Fourth', value: 4 },
        { label: 'Fifth', value: 5 },
      ],
    };
  },
  data() {
    return {
      loading: false,
      showDialog: false,
      editingEventId: null as number | null,
      editingIsDutch: false,
      eventTypes: [] as any[],
      form: {
        title: '',
        description: '',
        image_url: '',
        week_of_month: 1,
        weekday: 2,
        exclude_july_august: false,
        is_single_event: false,
        single_date: '',
        sort_order: 10,
        is_active: true,
      },
    };
  },
  async beforeMount() {
    await this.fetchEventTypes();
  },
  computed: {
    dialogIsDutch(): boolean {
      return !!this.editingEventId && this.editingIsDutch;
    },
    dialogLabels() {
      if (this.dialogIsDutch) {
        return {
          dialogTitle: 'Evenementtype bewerken',
          title: 'Titel',
          description: 'Beschrijving',
          imageUrl: 'Afbeeldings-URL (optioneel)',
          weekOfMonth: 'Week van de maand',
          weekday: 'Weekdag',
          excludeJulyAugust: 'Juli en augustus uitsluiten',
          singleEvent: 'Eenmalig evenement (geen weeknavigatie)',
          singleEventDate: 'Datum (eenmalig evenement)',
          sortOrder: 'Sorteervolgorde',
          cancel: 'Annuleren',
          save: 'Opslaan',
          updatedMessage: 'Evenementtype bijgewerkt',
          createdMessage: 'Evenementtype aangemaakt',
          weekdays: {
            0: 'Maandag',
            1: 'Dinsdag',
            2: 'Woensdag',
            3: 'Donderdag',
            4: 'Vrijdag',
            5: 'Zaterdag',
            6: 'Zondag',
          } as Record<number, string>,
          weeks: {
            1: 'Eerste',
            2: 'Tweede',
            3: 'Derde',
            4: 'Vierde',
            5: 'Vijfde',
          } as Record<number, string>,
        };
      }
      return {
        dialogTitle: this.editingEventId ? 'Edit Event Type' : 'Create Event Type',
        title: 'Title',
        description: 'Description',
        imageUrl: 'Image URL (optional)',
        weekOfMonth: 'Week of month',
        weekday: 'Weekday',
        excludeJulyAugust: 'Exclude July & August',
        singleEvent: 'Single event (no week navigation)',
        singleEventDate: 'Date (single event)',
        sortOrder: 'Sort order',
        cancel: 'Cancel',
        save: 'Save',
        updatedMessage: 'Event type updated',
        createdMessage: 'Event type created',
        weekdays: {
          0: 'Monday',
          1: 'Tuesday',
          2: 'Wednesday',
          3: 'Thursday',
          4: 'Friday',
          5: 'Saturday',
          6: 'Sunday',
        } as Record<number, string>,
        weeks: {
          1: 'First',
          2: 'Second',
          3: 'Third',
          4: 'Fourth',
          5: 'Fifth',
        } as Record<number, string>,
      };
    },
    dialogWeekdayOptions() {
      return this.weekdayOptions.map((option: { label: string; value: number }) => ({
        value: option.value,
        label: this.dialogLabels.weekdays[option.value] || option.label,
      }));
    },
    dialogWeekOptions() {
      return this.weekOptions.map((option: { label: string; value: number }) => ({
        value: option.value,
        label: this.dialogLabels.weeks[option.value] || option.label,
      }));
    },
  },
  methods: {
    isDutchEventTitle(title: string): boolean {
      const normalized = (title || '').toLowerCase();
      return normalized.includes('jeugd') || normalized.includes('junior');
    },
    capitalizeFirst(text: string): string {
      if (!text) return text;
      return text.charAt(0).toUpperCase() + text.slice(1);
    },
    ordinalDay(day: number): string {
      const mod10 = day % 10;
      const mod100 = day % 100;
      if (mod10 === 1 && mod100 !== 11) return `${day}st`;
      if (mod10 === 2 && mod100 !== 12) return `${day}nd`;
      if (mod10 === 3 && mod100 !== 13) return `${day}rd`;
      return `${day}th`;
    },
    formatDateForCard(eventType: any): string {
      const d = new Date(`${eventType.next_date}T00:00:00`);
      if (this.isDutchEventTitle(eventType.title)) {
        const raw = new Intl.DateTimeFormat('nl-NL', {
          weekday: 'long',
          day: 'numeric',
          month: 'long',
        }).format(d);
        return this.capitalizeFirst(raw);
      }
      const weekday = new Intl.DateTimeFormat('en-US', { weekday: 'long' }).format(d);
      const month = new Intl.DateTimeFormat('en-US', { month: 'long' }).format(d);
      return `${weekday} ${month} ${this.ordinalDay(d.getDate())}`;
    },
    nextDateLabel(eventType: any): string {
      const formattedDate = this.formatDateForCard(eventType);
      if (this.isDutchEventTitle(eventType.title)) {
        return `Eerstvolgende datum: ${formattedDate}`;
      }
      return `Next event: ${formattedDate}`;
    },
    resetForm() {
      this.form = {
        title: '',
        description: '',
        image_url: '',
        week_of_month: 1,
        weekday: 2,
        exclude_july_august: false,
        is_single_event: false,
        single_date: '',
        sort_order: 10,
        is_active: true,
      };
    },
    openCreateDialog() {
      this.editingEventId = null;
      this.editingIsDutch = false;
      this.resetForm();
      this.showDialog = true;
    },
    openEditDialog(eventType: any) {
      this.editingEventId = eventType.id;
      this.editingIsDutch = this.isDutchEventTitle(eventType.title || '');
      this.form = {
        title: eventType.title || '',
        description: eventType.description || '',
        image_url: eventType.image_url || '',
        week_of_month: eventType.week_of_month,
        weekday: eventType.weekday,
        exclude_july_august: eventType.exclude_july_august,
        is_single_event: Boolean(eventType.is_single_event),
        single_date: Boolean(eventType.is_single_event) ? (eventType.next_date || '') : '',
        sort_order: eventType.sort_order,
        is_active: eventType.is_active,
      };
      this.showDialog = true;
    },
    async fetchEventTypes() {
      this.loading = true;
      try {
        const resp = await this.$api.get('/api/event-types');
        this.eventTypes = resp.data;
      } finally {
        this.loading = false;
      }
    },
    goToEvent(eventType: any) {
      this.$router.push({
        path: `/events/${eventType.id}`,
        query: { date: eventType.next_date },
      });
    },
    heroStyle(imageUrl: string) {
      if (imageUrl) {
        return `background-image: linear-gradient(rgba(0,0,0,.45), rgba(0,0,0,.45)), url(${imageUrl});`;
      }
      return 'background: linear-gradient(120deg, #2f4858, #33658a);';
    },
    async saveEventType() {
      const payload: any = {
        ...this.form,
      };

      if (payload.is_single_event && payload.single_date) {
        const selected = new Date(`${payload.single_date}T00:00:00`);
        const dayOfWeek = selected.getDay();
        payload.weekday = (dayOfWeek + 6) % 7;
        payload.week_of_month = Math.floor((selected.getDate() - 1) / 7) + 1;
        payload.exclude_july_august = false;
      }

      delete payload.single_date;

      if (this.editingEventId) {
        await this.$api.patch(`/api/event-types/${this.editingEventId}`, payload);
        this.$q.notify({ type: 'positive', message: this.dialogLabels.updatedMessage });
      } else {
        await this.$api.post('/api/event-types', payload);
        this.$q.notify({ type: 'positive', message: this.dialogLabels.createdMessage });
      }
      this.showDialog = false;
      this.editingEventId = null;
      this.editingIsDutch = false;
      this.resetForm();
      await this.fetchEventTypes();
    },
  },
});
</script>

<style scoped>
.event-card {
  position: relative;
  width: 100%;
  border-radius: 14px;
  overflow: hidden;
}

.edit-event-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 5;
}

.event-hero {
  min-height: 180px;
  background-size: cover;
  background-position: center;
  display: flex;
  align-items: flex-end;
}

.event-overlay {
  width: 100%;
  padding: 14px;
}
</style>
