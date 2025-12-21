@echo off
REM This script starts the Celery worker and Celery Beat for local development.
REM Make sure you have Redis server running before executing this script.

REM Activate the virtual environment
call venv\Scripts\activate

REM Start Celery Worker (in a separate window)
start cmd /k "celery -A app.celery_app worker -l info -P solo"

REM Start Celery Beat (in another separate window)
start cmd /k "celery -A app.celery_app beat -l info"

REM Start Redis server (uncomment the line below if Redis is not already running)
sudo service redis-server start

REM Check if it's running
sudo service redis-server status

echo Celery Worker and Beat processes started.
echo Close the new command windows to stop the processes.
pause