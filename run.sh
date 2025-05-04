#!/bin/bash

# Start the FastAPI server in the background
echo "Starting FastAPI server..."
uvicorn api:app --host 0.0.0.0 --port 8000 &
API_PID=$!

# Wait a moment for the API to start
sleep 3

# Start the Streamlit app in the background
echo "Starting Streamlit app..."
streamlit run streamlit_app.py --server.port 8501 &
STREAMLIT_PID=$!

# Function to handle shutdown
function cleanup {
  echo "Shutting down services..."
  kill $API_PID
  kill $STREAMLIT_PID
  exit 0
}

# Register the cleanup function when script is terminated
trap cleanup SIGINT SIGTERM

echo "Services started:"
echo "API running at http://localhost:8000"
echo "Streamlit app running at http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop all services"

# Keep the script running
while true; do
  sleep 1
  # Check if processes are still running
  if ! ps -p $API_PID > /dev/null; then
    echo "API process died unexpectedly"
    kill $STREAMLIT_PID 2>/dev/null
    exit 1
  fi
  
  if ! ps -p $STREAMLIT_PID > /dev/null; then
    echo "Streamlit process died unexpectedly"
    kill $API_PID 2>/dev/null
    exit 1
  fi
done 