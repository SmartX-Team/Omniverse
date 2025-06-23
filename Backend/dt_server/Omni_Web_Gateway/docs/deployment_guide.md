# 개발 가이드 - 클라이언트 구현

이 문서는 Omni Web Gateway 백엔드 서버와 연동하는 클라이언트(Omniverse Extension, CesiumJS Web UI)를 개발하기 위한 가이드입니다.
클로드4 에게 다음 클로드 세션을 위해 정리해달라고 별도로 만든 문서 입니다.

---

## 1. Omniverse Extension 클라이언트 개발

### 1.1 기본 구조

Omniverse Extension은 Python 스크립트로 구현되며, 다음 역할을 수행합니다:
- Globe Anchor API를 사용하여 객체의 지리적 좌표 읽기
- WebSocket으로 백엔드 서버에 연결
- 1초마다 좌표 데이터 전송
- 서버로부터 객체 선택 명령 수신 및 처리

### 1.2 필수 의존성

```python
# Omniverse 환경에서 기본 제공
import omni.usd
from pxr import Sdf
from cesium.usd.plugins.CesiumUsdSchemas import GlobeAnchorAPI

# WebSocket 통신용 (설치 필요할 수 있음)
import asyncio
import websockets
import json
import threading
```

### 1.3 완전한 구현 예시

```python
import asyncio
import websockets
import json
import threading
import time
import omni.usd
from pxr import Sdf

# Cesium 확장이 로드된 후에 import
try:
    from cesium.usd.plugins.CesiumUsdSchemas import GlobeAnchorAPI
except ImportError:
    print("Error: Cesium for Omniverse extension not found")
    GlobeAnchorAPI = None

class OmniverseWebSocketClient:
    def __init__(self, server_url="ws://localhost:8000/ws", prim_path="/World/Husky_01"):
        self.server_url = server_url
        self.prim_path = prim_path
        self.websocket = None
        self.connected = False
        self.running = False
        
    async def connect_and_run(self):
        """서버에 연결하고 메인 루프 실행"""
        try:
            async with websockets.connect(self.server_url) as websocket:
                self.websocket = websocket
                self.connected = True
                print(f"Connected to {self.server_url}")
                
                # 클라이언트 등록
                await self.register_client()
                
                # 메시지 수신 태스크와 좌표 전송 태스크를 병렬 실행
                await asyncio.gather(
                    self.receive_messages(),
                    self.send_coordinates_loop()
                )
                
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            self.connected = False
            
    async def register_client(self):
        """클라이언트 타입 등록"""
        register_message = {
            "type": "client_register",
            "client_type": "omniverse_extension"
        }
        await self.websocket.send(json.dumps(register_message))
        print("Registration message sent")
        
    async def receive_messages(self):
        """서버로부터 메시지 수신 처리"""
        try:
            async for message in self.websocket:
                data = json.loads(message)
                await self.handle_message(data)
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
        except Exception as e:
            print(f"Error receiving message: {e}")
            
    async def handle_message(self, data):
        """수신된 메시지 처리"""
        message_type = data.get("type")
        
        if message_type == "ack":
            print(f"Acknowledgment received: {data}")
            
        elif message_type == "select_object":
            prim_path = data.get("prim_path")
            print(f"Object selection request: {prim_path}")
            # 메인 스레드에서 실행되어야 하는 Omniverse API 호출
            self.schedule_object_selection(prim_path)
            
        elif message_type == "error":
            error_code = data.get("error_code")
            error_message = data.get("error_message")
            print(f"Error received: {error_code} - {error_message}")
            
    def schedule_object_selection(self, prim_path):
        """객체 선택을 메인 스레드에서 실행하도록 스케줄링"""
        # Omniverse API는 메인 스레드에서만 안전하게 실행 가능
        def select_object():
            try:
                import omni.kit.selection
                selection = omni.kit.selection.get_selection()
                selection.set_selected_prim_paths([prim_path], False)
                print(f"Object selected in Omniverse: {prim_path}")
            except Exception as e:
                print(f"Error selecting object: {e}")
        
        # 메인 스레드에서 실행
        omni.kit.app.get_app().get_main_thread_dispatcher().queue(select_object)
        
    async def send_coordinates_loop(self):
        """1초마다 좌표 데이터 전송"""
        while self.connected:
            try:
                coords = self.get_object_coordinates()
                if coords:
                    message = {
                        "type": "coordinate_update",
                        "prim_path": self.prim_path,
                        "latitude": coords["latitude"],
                        "longitude": coords["longitude"], 
                        "height": coords["height"],
                        "metadata": coords.get("metadata", {})
                    }
                    await self.websocket.send(json.dumps(message))
                    print(f"Coordinates sent: {coords['latitude']:.6f}, {coords['longitude']:.6f}")
                    
            except Exception as e:
                print(f"Error sending coordinates: {e}")
                
            await asyncio.sleep(1.0)  # 1초 대기
            
    def get_object_coordinates(self):
        """Globe Anchor API를 사용하여 객체 좌표 읽기"""
        if not GlobeAnchorAPI:
            return None
            
        try:
            stage = omni.usd.get_context().get_stage()
            prim = stage.GetPrimAtPath(Sdf.Path(self.prim_path))
            
            if not prim.IsValid():
                print(f"Invalid prim path: {self.prim_path}")
                return None
                
            # Globe Anchor 적용/가져오기
            anchor = GlobeAnchorAPI.Apply(prim)
            if not anchor:
                print(f"Failed to get Globe Anchor for {self.prim_path}")
                return None
                
            # 좌표 읽기
            latitude = anchor.GetAnchorLatitudeAttr().Get()
            longitude = anchor.GetAnchorLongitudeAttr().Get()
            height = anchor.GetAnchorHeightAttr().Get()
            
            if latitude is None or longitude is None:
                print("Coordinates not available")
                return None
                
            return {
                "latitude": float(latitude),
                "longitude": float(longitude),
                "height": float(height or 0.0),
                "metadata": {
                    "timestamp": time.time(),
                    "prim_name": prim.GetName()
                }
            }
            
        except Exception as e:
            print(f"Error getting coordinates: {e}")
            return None
    
    def start_in_thread(self):
        """별도 스레드에서 WebSocket 클라이언트 시작"""
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.connect_and_run())
            
        self.thread = threading.Thread(target=run_async, daemon=True)
        self.thread.start()
        print("WebSocket client started in background thread")
    
    def stop(self):
        """클라이언트 중지"""
        self.connected = False
        self.running = False

# 사용법
def start_websocket_client():
    """Omniverse Extension에서 호출할 함수"""
    client = OmniverseWebSocketClient(
        server_url="ws://localhost:8000/ws",
        prim_path="/World/Husky_01"  # 실제 객체 경로로 변경
    )
    client.start_in_thread()
    return client

# Extension 스크립트에서 실행
if __name__ == "__main__":
    client = start_websocket_client()
```

### 1.4 Extension으로 패키징 (선택사항)

완전한 Omniverse Extension으로 만들려면 다음 구조를 사용하세요:

```
com.company.omni_web_gateway/
├── config/
│   └── extension.toml
├── data/
└── omni/
    └── company/
        └── omni_web_gateway/
            ├── __init__.py
            └── extension.py
```

**extension.toml**
```toml
[package]
title = "Omni Web Gateway Extension"
description = "WebSocket client for real-time coordinate streaming"
version = "1.0.0"

[dependencies]
"omni.usd" = {}
"cesium.usd" = {}
```

---

## 2. CesiumJS Web UI 클라이언트 개발

### 2.1 기본 구조

CesiumJS Web UI는 HTML/JavaScript로 구현되며, 다음 역할을 수행합니다:
- CesiumJS를 사용한 2D/3D 지도 렌더링
- WebSocket으로 백엔드 서버에 연결
- 좌표 데이터 수신하여 지도에 마커 표시
- 마커 클릭 시 객체 선택 명령 전송

### 2.2 필수 의존성

```html
<!-- CesiumJS -->
<script src="https://cesium.com/downloads/cesiumjs/releases/1.111/Build/Cesium/Cesium.js"></script>
<link href="https://cesium.com/downloads/cesiumjs/releases/1.111/Build/Cesium/Widgets/widgets.css" rel="stylesheet">

<!-- 또는 npm 설치 -->
<!-- npm install cesium -->
```

### 2.3 완전한 구현 예시

**index.html**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Omni Web Gateway - CesiumJS Client</title>
    
    <!-- CesiumJS -->
    <script src="https://cesium.com/downloads/cesiumjs/releases/1.111/Build/Cesium/Cesium.js"></script>
    <link href="https://cesium.com/downloads/cesiumjs/releases/1.111/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
    
    <style>
        html, body, #cesiumContainer {
            width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden;
        }
        
        #status {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(42, 42, 42, 0.8);
            color: white;
            padding: 10px;
            border-radius: 5px;
            font-family: monospace;
            z-index: 1000;
        }
        
        .status-connected { color: #00ff00; }
        .status-disconnected { color: #ff0000; }
        .status-connecting { color: #ffff00; }
    </style>
</head>
<body>
    <div id="cesiumContainer"></div>
    
    <div id="status">
        <div>Status: <span id="connectionStatus" class="status-disconnected">Disconnected</span></div>
        <div>Objects: <span id="objectCount">0</span></div>
        <div>Server: <span id="serverUrl">-</span></div>
    </div>
    
    <script src="js/websocket-client.js"></script>
    <script src="js/cesium-map.js"></script>
    <script src="js/main.js"></script>
</body>
</html>
```

**js/websocket-client.js**
```javascript
class WebSocketClient {
    constructor(serverUrl = 'ws://localhost:8000/ws') {
        this.serverUrl = serverUrl;
        this.ws = null;
        this.connected = false;
        this.registered = false;
        this.onMessage = null;
        this.onStatusChange = null;
        this.reconnectInterval = 5000; // 5초
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
    }
    
    connect() {
        this.updateStatus('connecting');
        
        try {
            this.ws = new WebSocket(this.serverUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.connected = true;
                this.reconnectAttempts = 0;
                this.updateStatus('connected');
                this.register();
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('Error parsing message:', error);
                }
            };
            
            this.ws.onclose = (event) => {
                console.log('WebSocket disconnected:', event.code, event.reason);
                this.connected = false;
                this.registered = false;
                this.updateStatus('disconnected');
                this.scheduleReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateStatus('disconnected');
            };
            
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.updateStatus('disconnected');
            this.scheduleReconnect();
        }
    }
    
    register() {
        const message = {
            type: 'client_register',
            client_type: 'web_ui'
        };
        this.send(message);
    }
    
    send(data) {
        if (this.connected && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
            return true;
        } else {
            console.warn('WebSocket not connected, message not sent:', data);
            return false;
        }
    }
    
    sendObjectSelection(primPath) {
        const message = {
            type: 'select_object',
            prim_path: primPath
        };
        
        if (this.send(message)) {
            console.log('Object selection sent:', primPath);
        }
    }
    
    handleMessage(data) {
        console.log('Received message:', data);
        
        switch (data.type) {
            case 'ack':
                if (data.original_type === 'client_register') {
                    this.registered = true;
                    console.log('Client registered successfully');
                }
                break;
                
            case 'coordinate_update':
                if (this.onMessage) {
                    this.onMessage('coordinate_update', data);
                }
                break;
                
            case 'error':
                console.error('Server error:', data.error_code, data.error_message);
                break;
                
            default:
                console.warn('Unknown message type:', data.type);
        }
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Reconnecting in ${this.reconnectInterval/1000}s (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            
            setTimeout(() => {
                this.connect();
            }, this.reconnectInterval);
        } else {
            console.error('Max reconnection attempts reached');
        }
    }
    
    updateStatus(status) {
        if (this.onStatusChange) {
            this.onStatusChange(status);
        }
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
}
```

**js/cesium-map.js**
```javascript
class CesiumMap {
    constructor(containerId) {
        // Cesium Ion 액세스 토큰 설정 (실제 토큰으로 교체 필요)
        Cesium.Ion.defaultAccessToken = 'YOUR_CESIUM_ION_ACCESS_TOKEN';
        
        // Cesium Viewer 초기화
        this.viewer = new Cesium.Viewer(containerId, {
            terrainProvider: Cesium.createWorldTerrain(),
            imageryProvider: new Cesium.OpenStreetMapImageryProvider({
                url: 'https://a.tile.openstreetmap.org/'
            }),
            baseLayerPicker: false,
            vrButton: false,
            geocoder: false,
            homeButton: false,
            sceneModePicker: false,
            navigationHelpButton: false,
            animation: false,
            timeline: false,
            fullscreenButton: false,
            scene3DOnly: true
        });
        
        // 초기 카메라 위치 설정 (서울)
        this.viewer.camera.setView({
            destination: Cesium.Cartesian3.fromDegrees(127.0276, 37.4979, 10000),
            orientation: {
                heading: 0.0,
                pitch: -Cesium.Math.PI_OVER_TWO,
                roll: 0.0
            }
        });
        
        // 객체 추적용 엔티티 저장소
        this.entities = new Map();
        
        // 클릭 이벤트 핸들러
        this.onEntityClick = null;
        this.setupClickHandler();
    }
    
    setupClickHandler() {
        this.viewer.cesiumWidget.screenSpaceEventHandler.setInputAction((event) => {
            const picked = this.viewer.scene.pick(event.position);
            
            if (Cesium.defined(picked) && Cesium.defined(picked.id)) {
                const entity = picked.id;
                const primPath = entity.primPath;
                
                if (primPath && this.onEntityClick) {
                    console.log('Entity clicked:', primPath);
                    this.onEntityClick(primPath);
                }
            }
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
    }
    
    updateObjectPosition(primPath, latitude, longitude, height = 0, metadata = {}) {
        const position = Cesium.Cartesian3.fromDegrees(longitude, latitude, height);
        
        if (this.entities.has(primPath)) {
            // 기존 엔티티 업데이트
            const entity = this.entities.get(primPath);
            entity.position = position;
            
            // 메타데이터 업데이트
            if (metadata.speed !== undefined) {
                entity.description = `Speed: ${metadata.speed} m/s<br>Height: ${height.toFixed(1)}m`;
            }
            
        } else {
            // 새 엔티티 생성
            const entity = this.viewer.entities.add({
                id: primPath,
                name: this.getObjectName(primPath),
                position: position,
                primPath: primPath, // 커스텀 속성
                
                // 빌보드 (아이콘)
                billboard: {
                    image: this.getObjectIcon(primPath),
                    width: 32,
                    height: 32,
                    heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
                    verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
                    scaleByDistance: new Cesium.NearFarScalar(1000, 1.0, 10000, 0.5)
                },
                
                // 라벨
                label: {
                    text: this.getObjectName(primPath),
                    font: '12pt monospace',
                    fillColor: Cesium.Color.WHITE,
                    outlineColor: Cesium.Color.BLACK,
                    outlineWidth: 2,
                    pixelOffset: new Cesium.Cartesian2(0, -40),
                    showBackground: true,
                    backgroundColor: Cesium.Color.BLACK.withAlpha(0.7)
                },
                
                // 설명
                description: `Latitude: ${latitude.toFixed(6)}<br>Longitude: ${longitude.toFixed(6)}<br>Height: ${height.toFixed(1)}m`
            });
            
            this.entities.set(primPath, entity);
            console.log(`New entity created: ${primPath}`);
        }
    }
    
    getObjectName(primPath) {
        // Prim 경로에서 객체 이름 추출
        const parts = primPath.split('/');
        return parts[parts.length - 1] || 'Unknown Object';
    }
    
    getObjectIcon(primPath) {
        // 객체 타입에 따른 아이콘 선택
        if (primPath.includes('Husky')) {
            return 'data:image/svg+xml;base64,' + btoa(`
                <svg width="32" height="32" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="16" cy="16" r="12" fill="#ff6b35" stroke="#fff" stroke-width="2"/>
                    <circle cx="16" cy="16" r="6" fill="#fff"/>
                </svg>
            `);
        }
        
        // 기본 아이콘
        return 'data:image/svg+xml;base64,' + btoa(`
            <svg width="32" height="32" xmlns="http://www.w3.org/2000/svg">
                <rect x="4" y="4" width="24" height="24" fill="#4fc3f7" stroke="#fff" stroke-width="2"/>
                <circle cx="16" cy="16" r="4" fill="#fff"/>
            </svg>
        `);
    }
    
    removeObject(primPath) {
        if (this.entities.has(primPath)) {
            const entity = this.entities.get(primPath);
            this.viewer.entities.remove(entity);
            this.entities.delete(primPath);
            console.log(`Entity removed: ${primPath}`);
        }
    }
    
    flyToObject(primPath) {
        if (this.entities.has(primPath)) {
            const entity = this.entities.get(primPath);
            this.viewer.flyTo(entity, {
                duration: 2.0,
                offset: new Cesium.HeadingPitchRange(0, -Cesium.Math.PI_OVER_TWO, 1000)
            });
        }
    }
    
    getObjectCount() {
        return this.entities.size;
    }
}
```

**js/main.js**
```javascript
class OmniWebGatewayClient {
    constructor() {
        this.wsClient = null;
        this.cesiumMap = null;
        this.initialize();
    }
    
    initialize() {
        // CesiumJS 지도 초기화
        this.cesiumMap = new CesiumMap('cesiumContainer');
        
        // 엔티티 클릭 이벤트 핸들러 설정
        this.cesiumMap.onEntityClick = (primPath) => {
            this.handleEntityClick(primPath);
        };
        
        // WebSocket 클라이언트 초기화
        this.wsClient = new WebSocketClient('ws://localhost:8000/ws');
        
        // WebSocket 메시지 핸들러 설정
        this.wsClient.onMessage = (type, data) => {
            this.handleWebSocketMessage(type, data);
        };
        
        // 상태 변경 핸들러 설정
        this.wsClient.onStatusChange = (status) => {
            this.updateUI(status);
        };
        
        // WebSocket 연결 시작
        this.wsClient.connect();
        
        // UI 초기 설정
        this.setupUI();
    }
    
    handleWebSocketMessage(type, data) {
        switch (type) {
            case 'coordinate_update':
                this.cesiumMap.updateObjectPosition(
                    data.prim_path,
                    data.latitude,
                    data.longitude,
                    data.height || 0,
                    data.metadata || {}
                );
                this.updateObjectCount();
                break;
                
            default:
                console.log('Unhandled message type:', type, data);
        }
    }
    
    handleEntityClick(primPath) {
        console.log('Object selected:', primPath);
        
        // 서버로 객체 선택 명령 전송
        this.wsClient.sendObjectSelection(primPath);
        
        // 해당 객체로 카메라 이동
        this.cesiumMap.flyToObject(primPath);
    }
    
    setupUI() {
        document.getElementById('serverUrl').textContent = this.wsClient.serverUrl;
        this.updateObjectCount();
    }
    
    updateUI(status) {
        const statusElement = document.getElementById('connectionStatus');
        statusElement.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        statusElement.className = `status-${status}`;
    }
    
    updateObjectCount() {
        document.getElementById('objectCount').textContent = this.cesiumMap.getObjectCount();
    }
}

// 애플리케이션 시작
document.addEventListener('DOMContentLoaded', () => {
    const app = new OmniWebGatewayClient();
    
    // 전역 변수로 설정 (디버깅용)
    window.omniApp = app;
});
```

### 2.4 정적 웹 서버 실행

**package.json** (선택사항)
```json
{
  "name": "omni-web-gateway-client",
  "version": "1.0.0",
  "description": "CesiumJS client for Omni Web Gateway",
  "scripts": {
    "start": "npx http-server . -p 3000 -c-1",
    "dev": "npx http-server . -p 3000 -c-1 --cors"
  },
  "dependencies": {
    "cesium": "^1.111.0"
  },
  "devDependencies": {
    "http-server": "^14.1.1"
  }
}
```

**실행 방법**
```bash
# 간단한 HTTP 서버 실행
npx http-server . -p 3000

# 또는 Python 서버
python -m http.server 3000

# 브라우저에서 http://localhost:3000 접속
```

---

## 3. 통합 테스트 시나리오

### 3.1 전체 시스템 실행 순서

1. **백엔드 서버 시작**
   ```bash
   cd backend
   python -m app.main
   ```

2. **Web UI 서버 시작**
   ```bash
   cd web-ui
   npx http-server . -p 3000
   ```

3. **Omniverse Extension 실행**
   - Omniverse에서 Extension 스크립트 실행
   - 또는 독립 Python 스크립트로 실행

4. **브라우저에서 Web UI 접속**
   - `http://localhost:3000` 접속
   - WebSocket 연결 상태 확인

### 3.2 테스트 체크리스트

- [ ] 백엔드 서버 정상 시작 (`http://localhost:8000/api/health` 확인)
- [ ] Web UI WebSocket 연결 성공
- [ ] Omniverse Extension WebSocket 연결 성공
- [ ] 좌표 데이터가 1초마다 Web UI에 표시됨
- [ ] Web UI에서 마커 클릭 시 Omniverse에서 객체 선택됨
- [ ] 연결 해제/재연결 테스트
- [ ] 에러 처리 테스트

### 3.3 디버깅 팁

**백엔드 서버 로그 확인**
```bash
# 자세한 로그 출력
LOG_LEVEL=DEBUG python -m app.main
```

**브라우저 개발자 도구**
- Console에서 WebSocket 연결 상태 확인
- Network 탭에서 WebSocket 메시지 모니터링

**Omniverse Extension 로그**
- Omniverse Console 창에서 Python 출력 확인
- Extension Manager에서 로그 확인

---

## 4. 다음 단계 개발 가이드

### 4.1 기능 확장

**다중 객체 지원**
- 여러 Husky 로봇 동시 추적
- 객체별 상태 정보 표시

**실시간 경로 표시**
- 객체 이동 경로를 선(Polyline)으로 표시
- 과거 위치 히스토리 저장

**상태 정보 확장**
- 배터리 레벨, 속도, 방향 등
- 알람 및 경고 메시지

### 4.2 성능 최적화

**데이터 압축**
- 좌표 정밀도 조절
- 변화가 없는 데이터 필터링

**연결 관리**
- 재연결 로직 개선
- 연결 풀링

**렌더링 최적화**
- 대량 객체