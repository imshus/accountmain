@echo off
rem Run the Accounts.ai backend so the Android app (or another computer) can reach it over your network.
rem The app asks for the address printed below. There is no password: use it on a network you trust.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Set up the backend first:
  echo   python -m venv .venv
  echo   .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)
if "%PORT%"=="" set PORT=8000
.venv\Scripts\python.exe -c "import socket; ips = sorted({a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)} - {'127.0.0.1'}); print(); print('In the app, enter this server address: ' + '  or  '.join('http://%%s:%PORT%' %% ip for ip in ips)); print()"
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port %PORT%
