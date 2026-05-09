/**
 * FCM token helper. Initialized by the firebase boot file so components
 * can call getFCMToken() without importing the boot module (avoids circular deps).
 */
import type { Messaging } from 'firebase/messaging';
import { getToken } from 'firebase/messaging';
import { getApps, initializeApp } from 'firebase/app';
import { getMessaging, isSupported } from 'firebase/messaging';
import { getFirebaseWebConfig, getMissingFirebaseConfigKeys } from './firebaseConfig';

let messagingInstance: Messaging | null = null;
let vapidKeyValue: string | undefined;

export function initFCM(messaging: Messaging, vapidKey: string | undefined): void {
  messagingInstance = messaging;
  vapidKeyValue = vapidKey;
}

async function ensureMessagingInitialized(): Promise<void> {
  if (messagingInstance) {
    return;
  }

  const supported = await isSupported();
  if (!supported) {
    throw new Error('Firebase messaging is not supported in this browser.');
  }

  const firebaseConfig = getFirebaseWebConfig();
  const missingConfig = getMissingFirebaseConfigKeys(firebaseConfig);
  if (missingConfig.length > 0) {
    throw new Error(
      `Missing Firebase app config: ${missingConfig.join(', ')}. ` +
      'Set FB_* values in frontend/.env and restart Quasar dev server.'
    );
  }

  const app = getApps().length > 0 ? getApps()[0] : initializeApp(firebaseConfig);
  messagingInstance = getMessaging(app);
}

export async function getFCMToken(): Promise<string | null> {
  await ensureMessagingInitialized();

  if (!vapidKeyValue) {
    throw new Error('Missing Firebase VAPID key (FB_VAPID_KEY).');
  }

  if (!('serviceWorker' in navigator)) {
    throw new Error('Service workers are not supported in this browser.');
  }

  const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
  await navigator.serviceWorker.ready;

  return getToken(messagingInstance, {
    vapidKey: vapidKeyValue,
    serviceWorkerRegistration: registration,
  });
}

export async function enablePushNotifications(apiClient: any, q: any): Promise<boolean> {
  if (typeof Notification === 'undefined') {
    q.notify({
      color: 'negative',
      message: 'Your browser does not support push notifications.',
      icon: 'notifications_off',
    });
    return false;
  }

  try {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') {
      q.notify({
        color: 'negative',
        message: 'Permission denied for notifications.',
        icon: 'notifications_off',
      });
      return false;
    }

    const token = await getFCMToken();
    if (!token) {
      q.notify({
        color: 'warning',
        message: 'Could not get notification token. Check Firebase Web Push settings.',
      });
      return false;
    }

    const response = await apiClient.post('/api/notifications/save-token', {
      token,
    });
    q.notify({
      color: 'positive',
      message: response.data?.message || 'Notifications linked!',
      icon: 'notifications_active',
    });
    return true;
  } catch (err) {
    console.error('Error enabling notifications:', err);
    const details = err instanceof Error ? err.message : '';
    q.notify({
      color: 'negative',
      message: details
        ? `Failed to enable notifications: ${details}`
        : 'Failed to enable notifications.',
    });
    return false;
  }
}
