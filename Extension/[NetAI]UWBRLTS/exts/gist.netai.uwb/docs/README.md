# NetAI UWB Real-time Tracking Extension

This is the 2025 updated version of the Omniverse Extension for real-time UWB tracking systems.

## Installation & Configuration

### 1. Install Dependencies
The extension depends on the following Python packages:
- `requests>=2.25.0`
- `httpx>=0.24.0`
- `aiokafka>=0.8.0`
- `psycopg2-binary>=2.9.0`
- `numpy>=1.21.0`

### 2. Create Configuration File
Unlike typical containers, the extension code injects dependency information in the form of config.json.
Copy 'uwbrtls/config.json.example' to 'uwbrtls/config.json' and modify it to fit your environment.

```bash
cp uwbrtls/config.json.example uwbrtls/config.json