# Omni Web Gateway Backend

WebSocket relay server for real-time bidirectional communication between NVIDIA Omniverse and web-based 2D map applications.

## Overview

This backend server acts as a middleware that enables real-time data exchange between:
- **Omniverse Extensions** (Python scripts running inside Omniverse)
- **Web UI Applications** (Browser-based clients using CesiumJS or similar mapping libraries)

### Architecture

```
Omniverse Extension  <--WebSocket-->  Backend Server  <--WebSocket-->  Web UI Client
     (Python)                         (FastAPI)                        (JavaScript)
```

## Key Features

- **Real-time WebSocket Communication**: Maintains persistent connections with multiple clients
- **Client Type Management**: Distinguishes between Omniverse extensions and web UI clients
- **Message Routing**: Routes messages between different client types based on message content
- **Data Validation**: Validates coordinate data and message formats using Pydantic models
- **Health Monitoring**: Provides health check endpoints for monitoring and deployment

## Message Flow

### Coordinate Updates (Omniverse → Web)
1. Omniverse extension reads object coordinates using Globe Anchor API
2. Extension sends coordinate data to backend via WebSocket
3. Backend validates and broadcasts data to all connected web clients
4. Web clients update map markers in real-time

### Object Selection (Web → Omniverse)
1. User clicks on map marker in web UI
2. Web client sends selection command to backend
3. Backend forwards command to Omniverse extension
4. Extension highlights selected object in Omniverse viewport

## API Endpoints

### WebSocket
- **Endpoint**: `ws://localhost:8000/ws`
- **Purpose**: Main communication channel for all clients

### REST API
- **Health Check**: `GET /api/health` - Server status verification
- **Status**: `GET /api/status` - Connection statistics and client information

## Message Protocol

### Client Registration
```json
{
  "type": "client_register",
  "client_type": "omniverse_extension" | "web_ui"
}
```

### Coordinate Update
```json
{
  "type": "coordinate_update",
  "prim_path": "/World/Husky_01",
  "latitude": 37.123456,
  "longitude": 127.654321,
  "height": 100.0,
  "metadata": {}
}
```

### Object Selection
```json
{
  "type": "select_object",
  "prim_path": "/World/Husky_01"
}
```

### Error Response
```json
{
  "type": "error",
  "error_code": "INVALID_MESSAGE_TYPE",
  "error_message": "Unknown message type: invalid_type"
}
```

## Installation & Setup

### Prerequisites
- Python 3.11+
- pip

### Local Development

1. **Clone and navigate to backend directory**
```bash
cd backend
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Create environment file**
```bash
cp .env.example .env
```

4. **Run the server**
```bash
python -m app.main
```

### Using Scripts

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Setup development environment
./scripts/setup.sh

# Run development server
./scripts/run_dev.sh

# Run tests
./scripts/test.sh
```

## Docker Deployment

### Build Image
```bash
docker build -t omni-web-gateway-backend .
```

### Run Container
```bash
docker run -d \
  --name omni-backend \
  -p 8000:8000 \
  -e DEBUG=false \
  -e LOG_LEVEL=INFO \
  omni-web-gateway-backend
```

### Using Docker Compose
```bash
docker-compose up -d
```

## Configuration

Environment variables can be set in `.env` file or passed directly:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `8000` | Server port |
| `DEBUG` | `true` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_FORMAT` | `json` | Log format (json, plain) |
| `CORS_ALLOW_ALL` | `true` | Allow all origins (testing only) |

## Development

### Project Structure
```
backend/
├── app/
│   ├── core/           # Configuration and utilities
│   ├── websocket/      # WebSocket management and handlers
│   ├── models/         # Pydantic data models
│   ├── services/       # Business logic
│   ├── api/           # REST API endpoints
│   └── utils/         # Helper functions
├── tests/             # Test files
├── scripts/           # Utility scripts
└── requirements.txt   # Dependencies
```

### Adding New Message Types

1. Define message model in `app/models/message.py`
2. Add handler method in `app/websocket/handlers.py`
3. Update message routing logic in `handle_message()` method

### Testing

Run tests with coverage:
```bash
./scripts/test.sh
```

Or manually:
```bash
pip install -r requirements-dev.txt
pytest tests/ -v --cov=app
```

## Security Considerations

**Current State**: CORS is set to allow all origins for development/testing purposes.

**Production Requirements**:
- Restrict CORS origins to specific domains
- Implement authentication/authorization
- Use HTTPS/WSS for encrypted communication
- Add rate limiting
- Validate and sanitize all input data

## Troubleshooting

### Common Issues

1. **WebSocket connection fails**
   - Check if server is running on correct port
   - Verify firewall settings
   - Ensure CORS settings allow client origin

2. **Messages not routing**
   - Confirm client registration with correct `client_type`
   - Check server logs for validation errors
   - Verify message format matches protocol

3. **High memory usage**
   - Monitor number of connected clients
   - Check for WebSocket connection leaks
   - Review message queuing and processing

### Logs

Server logs include:
- Client connection/disconnection events
- Message routing information
- Validation errors
- Performance metrics

Set `LOG_LEVEL=DEBUG` for detailed debugging information.