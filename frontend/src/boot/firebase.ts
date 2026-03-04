import { boot } from 'quasar/wrappers';
import { initializeApp } from 'firebase/app';
import { getMessaging, getToken, Messaging } from 'firebase/messaging';

// 1. Get these values from your Firebase Console:
// Project Settings > General > Your Apps (Web App)
const firebaseConfig = {
  apiKey: process.env.FIREBASE_API_KEY,
  authDomain: process.env.FIREBASE_AUTH_DOMAIN,
  projectId: process.env.FIREBASE_PROJECT_ID,
  storageBucket: process.env.FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.FIREBASE_APP_ID,
  measurementId: process.env.FIREBASE_MEASUREMENT_ID
};

// 2. Initialize Firebase
const firebaseApp = initializeApp(firebaseConfig);
const messaging = getMessaging(firebaseApp);

// 3. Extend the Vue interface so TypeScript knows about $messaging
declare module '@vue/runtime-core' {
  interface ComponentCustomProperties {
    $messaging: Messaging;
  }
}

export default boot(({ app }) => {
  // This makes this.$messaging available in all your components
  app.config.globalProperties.$messaging = messaging;
});

// We export these for direct use in the component logic
export { messaging, getToken };