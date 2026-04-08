import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

// All values are read from Vite environment variables.
// Add these to your .env file (copy from Firebase project settings → SDK config):
//
//   VITE_FIREBASE_API_KEY=...
//   VITE_FIREBASE_AUTH_DOMAIN=...
//   VITE_FIREBASE_PROJECT_ID=...
//   VITE_FIREBASE_STORAGE_BUCKET=...
//   VITE_FIREBASE_MESSAGING_SENDER_ID=...
//   VITE_FIREBASE_APP_ID=...
//
const firebaseConfig = {
    apiKey:            import.meta.env.VITE_FIREBASE_API_KEY || "dummy-api-key",
    authDomain:        import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "dummy-auth-domain",
    projectId:         import.meta.env.VITE_FIREBASE_PROJECT_ID || "dummy-project-id",
    storageBucket:     import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "dummy-storage-bucket",
    messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "dummy-sender-id",
    appId:             import.meta.env.VITE_FIREBASE_APP_ID || "dummy-app-id",
};

const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);

export const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: "select_account" });
