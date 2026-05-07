import { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    children: [
      { path: '', component: () => import('pages/EventSelectPage.vue') },
      { path: 'sessions', component: () => import('pages/PublicEventsPage.vue') },
      {
        path: 'events/:eventTypeId',
        component: () => import('pages/IndexPage.vue'),
        props: true,
      },
      // TODO: Put the date in the URL
      { path: 'profile', component: () => import('pages/ProfilePage.vue') },
      { path: 'signups', component: () => import('pages/SignupsPage.vue') },
      { path: 'admin/users', component: () => import('pages/AdminUsersPage.vue') },
      { path: 'admin/events', component: () => import('pages/AdminEventsPage.vue') },
      { path: 'faq', component: () => import('pages/FaqPage.vue') },
    ],
  },

  // Always leave this as last one,
  // but you can also remove it
  {
    path: '/:catchAll(.*)*',
    component: () => import('pages/ErrorNotFound.vue'),
  },
];

export default routes;
