@echo off
title GraphRAG Launcher
echo.
echo  Starting GraphRAG...
echo.

start "GraphRAG Backend" cmd /k "cd /d D:\RAG\GraphRAG\backend && call ..\venv\Scripts\activate.bat && uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload"

echo  Waiting for backend to initialize...
timeout /t 5 /nobreak >nul

start "GraphRAG Frontend" cmd /k "cd /d D:\RAG\GraphRAG\frontend && npm run dev"

echo.
echo  Backend  : http://localhost:8080
echo  Frontend : http://localhost:3000
echo  Neo4j    : http://localhost:7474
echo.
echo  Both services started in separate windows.
echo  Close those windows to stop the services.
echo.
pause
