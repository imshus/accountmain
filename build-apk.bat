@echo off
rem Builds the Android app (debug APK) from this folder: web app build -> Capacitor sync -> Gradle.
rem Needs Node.js and Android Studio (its bundled Java and the Android SDK). Result: apk\Accounts.ai-1.0-debug.apk
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%frontend" || goto :fail

if not exist node_modules (
    echo Installing the web app's packages...
    call npm ci || goto :fail
)

rem The server address is built into the app, and it comes only from VITE_API_URL in frontend\.env.
set "VITE_API_URL="
node scripts\check-server.mjs || goto :fail

echo [1/3] Building the web app...
call npm run build || goto :fail

echo [2/3] Copying it into the Android project...
call npx cap sync android || goto :fail

rem Android Studio's own Java and SDK, unless JAVA_HOME / ANDROID_HOME are already set.
if not defined JAVA_HOME if exist "%ProgramFiles%\Android\Android Studio\jbr\bin\java.exe" set "JAVA_HOME=%ProgramFiles%\Android\Android Studio\jbr"
if not defined ANDROID_HOME if exist "%LOCALAPPDATA%\Android\Sdk" set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
if not defined JAVA_HOME (
    echo Java not found: install Android Studio, or set JAVA_HOME to a JDK 21.
    goto :fail
)
if not defined ANDROID_HOME (
    echo Android SDK not found: install Android Studio, or set ANDROID_HOME.
    goto :fail
)

echo [3/3] Building the APK...
cd /d "%ROOT%frontend\android" || goto :fail
rem Full path: Windows may be set not to run programs from the current folder (NoDefaultCurrentDirectoryInExePath).
call "%ROOT%frontend\android\gradlew.bat" assembleDebug --console=plain || goto :fail

if not exist "%ROOT%apk" mkdir "%ROOT%apk"
copy /y "%ROOT%frontend\android\app\build\outputs\apk\debug\app-debug.apk" "%ROOT%apk\Accounts.ai-1.0-debug.apk" >nul || goto :fail
echo.
echo APK ready: %ROOT%apk\Accounts.ai-1.0-debug.apk
if not defined NO_PAUSE pause
exit /b 0

:fail
echo.
echo APK build failed - see the messages above.
rem Opened by double-click: keep the window open so the message can be read. NO_PAUSE=1 skips this.
if not defined NO_PAUSE pause
exit /b 1
