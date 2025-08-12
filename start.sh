#!/bin/bash

echo "🚀 Starting Financial Planning App..."
echo ""
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Function to clean up background processes on exit
cleanup() {
    echo ""
    echo "🛑 Stopping servers..."
    kill $(jobs -p) 2>/dev/null
    exit 0
}

# Set up trap to catch Ctrl+C
trap cleanup SIGINT SIGTERM

# Start backend in background
echo "📡 Starting backend server..."
cd backend && python main.py &
BACKEND_PID=$!

# Give backend a moment to start
sleep 2

# Start frontend in background  
echo "🎨 Starting frontend server..."
cd frontend && npm run dev &
FRONTEND_PID=$!

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
