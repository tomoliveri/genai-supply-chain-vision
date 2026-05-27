import { initializeApp, getApps, type FirebaseApp } from 'firebase/app';
import { getFirestore, type Firestore } from 'firebase/firestore';

function isConfigValid(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_FIREBASE_API_KEY &&
      process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN &&
      process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  );
}

let app: FirebaseApp | null = null;
let db: Firestore | null = null;

if (isConfigValid()) {
  const firebaseConfig = {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? 'traveltime-465606',
    storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
    messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
  };

  app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApps()[0];
  db = getFirestore(app);
} else {
  // Warn at module load time so the developer knows why data is empty.
  // Using typeof console to satisfy no-console linters while being explicit.
  if (typeof window !== 'undefined') {
    // Intentional warning: guides developers to configure credentials.
    // biome-ignore lint: intentional console.warn for developer guidance
    globalThis.console.warn(
      '[SupplyWatch] Firebase env vars are missing. ' +
        'Copy .env.local.example to .env.local and fill in your credentials.',
    );
  }
}

export { db };
