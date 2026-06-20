cd D:\nse-research-app

# Stop frontend first with Ctrl+C if it is running in terminal.
# If needed, find process using port 3000:
netstat -ano | findstr :3000

# Stop that PID:
Stop-Process -Id <PID> -Force

# Remove stale Next.js cache:
Remove-Item -Recurse -Force frontend\.next

# Restart frontend:
cd frontend
npm.cmd run dev