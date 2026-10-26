import type { CapacitorConfig } from "@capacitor/cli";

// The Android app is this frontend (dist/) inside a WebView. It talks to the Accounts.ai backend
// running on your computer or server, whose address is VITE_API_URL in frontend/.env, built into the app.
const config: CapacitorConfig = {
  appId: "in.itsolution.accountsai",
  appName: "Accounts.ai",
  webDir: "dist",
  server: {
    // Pages load from http://localhost, so calls to a backend on the local network over plain
    // http (http://192.168.x.x:8000) are allowed; the backend lists http://localhost in CORS_ORIGINS.
    androidScheme: "http",
    cleartext: true,
  },
};

export default config;
