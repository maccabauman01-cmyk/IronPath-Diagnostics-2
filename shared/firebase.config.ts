/**
 * Firebase client config — safe to commit (restricted by Firebase Auth / App Check).
 * Used by web app and shared with mobile via the same project.
 */
export const firebaseConfig = {
  apiKey: "AIzaSyCskE1_iiphOmnIYQ2Hg2ZsnzznnTaZlV4",
  authDomain: "ironpath-diagnostics.firebaseapp.com",
  projectId: "ironpath-diagnostics",
  storageBucket: "ironpath-diagnostics.firebasestorage.app",
  messagingSenderId: "420363825512",
  appId: "1:420363825512:web:35fbf1b930e7d8552da6dd",
  measurementId: "G-VZNJWPMWXY",
} as const;

export type FirebaseConfig = typeof firebaseConfig;
