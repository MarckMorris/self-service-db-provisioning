#!/bin/bash
echo "Starting Self-Service DB Provisioning Platform..."
docker-compose up -d
sleep 10

# Install dependencies
pip install fastapi uvicorn requests psycopg2-binary

# Start API in background
python src/provisioning_api.py &
API_PID=$!

# Wait for API to start
sleep 5

# Run demo client
python src/demo_client.py

# Stop API
kill $API_PID

echo "Demo complete! API stopped."
