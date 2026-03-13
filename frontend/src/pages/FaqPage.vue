<template>
  <q-page class="q-pa-md">
    <div class="text-h5 q-mb-md">Frequently Asked Questions</div>
    <q-list bordered class="rounded-borders">
      <q-expansion-item
        expand-separator
        icon="sym_o_priority"
        label="How does signup priority work?"
      >
        <q-card>
          <q-card-section>
            <div class="text-body2">
              <p>
                When signing up, choose priority 1, 2, or 3. The assignment system
                always handles higher priorities first.
              </p>
              <ul>
                <li>Priority 1 is processed before priority 2 and 3.</li>
                <li>If your preferred session is full, you can be assigned to another open one.</li>
                <li>If everything is full, you are put on the waiting list.</li>
              </ul>
            </div>
          </q-card-section>
        </q-card>
      </q-expansion-item>

      <q-expansion-item
        expand-separator
        icon="sym_o_cancel"
        label="Can I cancel my assignment?"
      >
        <q-card>
          <q-card-section>
            <div class="text-body2">
              <p>
                Yes. You can cancel your own assignment from the session card.
              </p>
              <ul>
                <li>Cancel only when needed, because your spot is released immediately.</li>
                <li>When a spot opens, players from waiting list can be promoted automatically.</li>
              </ul>
            </div>
          </q-card-section>
        </q-card>
      </q-expansion-item>

      <q-expansion-item
        expand-separator
        icon="sym_o_info"
        label="What notifications can I enable?"
      >
        <q-card>
          <q-card-section>
            <div class="text-body2">
              <p>
                You can toggle notifications from your profile page.
              </p>
              <ul>
                <li>Assignment release and waiting-list updates</li>
                <li>Admin reminders (release reminders and new-event notices)</li>
              </ul>
            </div>
          </q-card-section>
        </q-card>
      </q-expansion-item>
    </q-list>
  </q-page>
</template>
