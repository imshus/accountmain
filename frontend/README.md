# Accounts.ai frontend (web and Android app)

React + TypeScript (Vite), white-and-red theme. It holds no data and does no accounting itself: every
screen calls the backend's API. The same code runs as a website and, wrapped with Capacitor, as the
Android app.

## Web, for development

```bash
npm install
npm run dev          # http://localhost:5173 — /api is forwarded to the backend on 127.0.0.1:8000
```

Point it at another backend with `BACKEND_URL=http://host:8000 npm run dev`.

## Web, deployed

```bash
npm run build        # static files in dist/ — host them anywhere
```

Build with `VITE_API_URL=https://your-backend` (see `.env.example`) or leave it empty and set the server
address in the app (menu → Server). Add the site's address to the backend's `CORS_ORIGINS`.

## Android app (APK)

You need Android Studio (its SDK and bundled Java). From this folder:

```bash
npm run build
npx cap sync android
cd android
gradlew.bat assembleDebug    # -> android/app/build/outputs/apk/debug/app-debug.apk
```

Install the APK on a phone (allow "install unknown apps" for the file manager or browser you open it with).
On first start the app asks for the server address that `backend\start-server.bat` prints. CSV downloads open Android's share sheet (save to Files, send on WhatsApp or email).

For the Play Store, build a signed release instead: open `android/` in Android Studio →
Build → Generate Signed App Bundle / APK, and keep the keystore safe (updates must use the same key).
