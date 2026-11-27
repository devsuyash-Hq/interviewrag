# run.ps1 - starts backend (FastAPI) and frontend (Next.js)
$root = $PSScriptRoot

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; uv run uvicorn main:app --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"

Write-Host "Backend:  http://localhost:8000"
Write-Host "Frontend: http://localhost:3000"