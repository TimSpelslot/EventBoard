/**
 * FCM token helper. Initialized by the firebase boot file so components
 * can call getFCMToken() without importing the boot module (avoids circular deps).
 */
import type { Messaging } from 'firebase/messaging';
import { getToken } from 'firebase/messaging';

let messagingInstance: Messaging | null = null;
let vapidKeyValue: string | undefined;

export function initFCM(messaging: Messaging, vapidKey: string | undefined): void {
  messagingInstance = messaging;
  vapidKeyValue = vapidKey;
}

export async function getFCMToken(): Promise<string | null> {
  if (!messagingInstance) return null;
  return getToken(messagingInstance, { vapidKey: vapidKeyValue });
}
