# Omni Web Gateway API 명세서

## 개요

Omni Web Gateway는 NVIDIA Omniverse와 웹 기반 2D 지도 애플리케이션 간의 실시간 양방향 통신을 위한 WebSocket 기반 중계 서버입니다.

### 기본 정보
- **서버 주소**: `localhost:8000` (기본값) 필요시 알아서들 바꾸삼~~~
- **프로토콜**: WebSocket (ws://) 또는 WebSocket Secure (wss://)
- **메시지 형식**: JSON
- **인코딩**: UTF-8

---

## REST API 엔드포인트

### 1. 헬스 체크

#### `GET /api/health`

서버의 기본 상태를 확인

**응답**
```json
{
  "status": "healthy",
  "service": "Omni Web Gateway",
  "version": "1.0.0"
}
```

**상태 코드**
- `200 OK`: 서버 정상 동작

---

### 2. 서버 상태 조회

#### `GET /api/status`

서버 상태와 연결된 클라이언트 정보를 조회

**응답**
```json
{
  "status": "running",
  "clients": {
    "total": 3,
    "registered": 2,
    "omniverse_clients": 1,
    "web_clients": 1
  }
}
```

**응답 필드**
- `status`: 서버 실행 상태
- `clients.total`: 전체 연결된 클라이언트 수
- `clients.registered`: 등록 완료된 클라이언트 수
- `clients.omniverse_clients`: Omniverse Extension 클라이언트 수
- `clients.web_clients`: Web UI 클라이언트 수

**상태 코드**
- `200 OK`: 정상 응답

---

## WebSocket API

### 연결

#### `ws://localhost:8000/ws`

모든 클라이언트(Omniverse Extension, Web UI)는 이 단일 엔드포인트로 연결

**연결 과정**
1. WebSocket 연결 수립
2. 서버가 고유한 `client_id` 할당
3. 클라이언트가 등록 메시지 전송 (`client_register`)
4. 등록 완료 후 데이터 송수신 가능

---

## 메시지 프로토콜

### 기본 메시지 구조

모든 메시지는 다음 기본 필드를 포함:

```json
{
  "type": "message_type",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**공통 필드**
- `type` (string, 필수): 메시지 타입 식별자
- `timestamp` (string, 선택): ISO 8601 형식의 타임스탬프

---

### 1. 클라이언트 등록

#### `client_register`

클라이언트가 서버에 자신의 타입을 등록합니다. **연결 후 첫 번째로 보내야 하는 메시지**

**요청 (클라이언트 → 서버)**
```json
{
  "type": "client_register",
  "client_type": "omniverse_extension"
}
```

**필드**
- `client_type` (string, 필수): 클라이언트 타입
  - `"omniverse_extension"`: Omniverse에서 실행되는 Python 스크립트
  - `"web_ui"`: 웹 브라우저에서 실행되는 JavaScript 클라이언트

**응답 (서버 → 클라이언트)**
```json
{
  "type": "ack",
  "original_type": "client_register",
  "status": "success"
}
```

**에러 응답**
```json
{
  "type": "error",
  "error_code": "UNSUPPORTED_CLIENT_TYPE",
  "error_message": "Unsupported client type: invalid_type"
}
```

---

### 2. 좌표 업데이트

#### `coordinate_update`

Omniverse Extension이 객체의 지리적 좌표를 웹 클라이언트들에게 전송

**요청 (Omniverse Extension → 서버)**
```json
{
  "type": "coordinate_update",
  "prim_path": "/World/Husky_01",
  "latitude": 37.123456789,
  "longitude": 127.987654321,
  "height": 125.5,
  "metadata": {
    "speed": 2.5,
    "heading": 45.0,
    "battery": 85
  }
}
```

**필드**
- `prim_path` (string, 필수): Omniverse 씬에서 객체의 경로
- `latitude` (float, 필수): 위도 (-90 ~ 90)
- `longitude` (float, 필수): 경도 (-180 ~ 180)
- `height` (float, 선택): 높이 (미터, 기본값: 0.0)
- `metadata` (object, 선택): 추가 객체 정보

**전달 (서버 → Web UI 클라이언트들)**
```json
{
  "type": "coordinate_update",
  "prim_path": "/World/Husky_01",
  "latitude": 37.123456789,
  "longitude": 127.987654321,
  "height": 125.5,
  "metadata": {
    "speed": 2.5,
    "heading": 45.0,
    "battery": 85
  }
}
```

**제약사항**
- 오직 `omniverse_extension` 타입 클라이언트만 전송 가능
- 등록되지 않은 클라이언트는 전송 불가

**에러 응답**
```json
{
  "type": "error",
  "error_code": "UNAUTHORIZED",
  "error_message": "Only Omniverse Extension can send coordinate updates"
}
```

---

### 3. 객체 선택

#### `select_object`

Web UI 클라이언트가 Omniverse에서 특정 객체를 선택하도록 요청

**요청 (Web UI → 서버)**
```json
{
  "type": "select_object",
  "prim_path": "/World/Husky_01"
}
```

**필드**
- `prim_path` (string, 필수): 선택할 객체의 Omniverse 경로

**전달 (서버 → Omniverse Extension 클라이언트들)**
```json
{
  "type": "select_object",
  "prim_path": "/World/Husky_01"
}
```

**제약사항**
- 오직 `web_ui` 타입 클라이언트만 전송 가능
- 등록되지 않은 클라이언트는 전송 불가

**에러 응답**
```json
{
  "type": "error",
  "error_code": "UNAUTHORIZED",
  "error_message": "Only Web UI can send object selection commands"
}
```

---

### 4. 확인 응답

#### `ack`

서버가 클라이언트의 요청을 성공적으로 처리했음을 알림림

**응답 (서버 → 클라이언트)**
```json
{
  "type": "ack",
  "original_type": "client_register",
  "status": "success"
}
```

**필드**
- `original_type` (string): 원본 메시지의 타입
- `status` (string): 처리 상태 ("success", "failed")

---

### 5. 에러 응답

#### `error`

서버에서 클라이언트로 에러 정보를 전송합니다.

**응답 (서버 → 클라이언트)**
```json
{
  "type": "error",
  "error_code": "INVALID_MESSAGE_TYPE",
  "error_message": "Unknown message type: invalid_type"
}
```

**필드**
- `error_code` (string): 에러 코드
- `error_message` (string): 에러 상세 메시지

**에러 코드 목록**
- `INVALID_JSON`: JSON 파싱 실패
- `UNKNOWN_MESSAGE_TYPE`: 지원하지 않는 메시지 타입
- `INVALID_MESSAGE_FORMAT`: 메시지 형식 오류
- `CLIENT_NOT_REGISTERED`: 등록되지 않은 클라이언트
- `UNSUPPORTED_CLIENT_TYPE`: 지원하지 않는 클라이언트 타입
- `UNAUTHORIZED`: 권한 없는 작업 시도
- `COORDINATE_UPDATE_FAILED`: 좌표 업데이트 처리 실패
- `OBJECT_SELECTION_FAILED`: 객체 선택 처리 실패
- `REGISTRATION_FAILED`: 클라이언트 등록 실패
- `INTERNAL_ERROR`: 서버 내부 오류

---

## 사용 시나리오

### 시나리오 1: Omniverse Extension 연결 및 좌표 전송

```
1. Extension → Server: WebSocket 연결
2. Extension → Server: {"type": "client_register", "client_type": "omniverse_extension"}
3. Server → Extension: {"type": "ack", "original_type": "client_register", "status": "success"}
4. Extension → Server: {"type": "coordinate_update", "prim_path": "/World/Husky_01", ...}
5. Server → All Web Clients: {"type": "coordinate_update", "prim_path": "/World/Husky_01", ...}
```

### 시나리오 2: Web UI 클라이언트 연결 및 객체 선택

```
1. Web UI → Server: WebSocket 연결
2. Web UI → Server: {"type": "client_register", "client_type": "web_ui"}
3. Server → Web UI: {"type": "ack", "original_type": "client_register", "status": "success"}
4. Web UI → Server: {"type": "select_object", "prim_path": "/World/Husky_01"}
5. Server → All Omniverse Clients: {"type": "select_object", "prim_path": "/World/Husky_01"}
```

### 시나리오 3: 에러 처리

```
1. Client → Server: 잘못된 JSON 형식 메시지
2. Server → Client: {"type": "error", "error_code": "INVALID_JSON", "error_message": "Invalid JSON format"}
```

---

## 클라이언트 구현 예시

### JavaScript (Web UI)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onopen = function() {
    // 클라이언트 등록
    ws.send(JSON.stringify({
        type: 'client_register',
        client_type: 'web_ui'
    }));
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    if (data.type === 'coordinate_update') {
        // 지도에 마커 업데이트
        updateMapMarker(data.prim_path, data.latitude, data.longitude);
    }
};

// 객체 선택 요청
function selectObject(primPath) {
    ws.send(JSON.stringify({
        type: 'select_object',
        prim_path: primPath
    }));
}
```

### Python (Omniverse Extension)

```python
import asyncio
import websockets
import json

async def omniverse_client():
    uri = "ws://localhost:8000/ws"
    
    async with websockets.connect(uri) as websocket:
        # 클라이언트 등록
        await websocket.send(json.dumps({
            "type": "client_register",
            "client_type": "omniverse_extension"
        }))
        
        # 좌표 전송 루프
        while True:
            coords = get_object_coordinates()  # 좌표 읽기 함수
            
            await websocket.send(json.dumps({
                "type": "coordinate_update",
                "prim_path": "/World/Husky_01",
                "latitude": coords.lat,
                "longitude": coords.lng,
                "height": coords.height
            }))
            
            await asyncio.sleep(1)  # 1초마다 전송

asyncio.run(omniverse_client())
```

---

## 제한사항 및 고려사항

### 보안
- 현재 CORS는 모든 오리진을 허용 (개발/테스트용)
- 프로덕션 환경에서는 특정 도메인으로 제한 필요
- 인증/인가 메커니즘 구현 권장

### 성능
- 클라이언트 수에 따른 메모리 사용량 증가
- 대량의 좌표 업데이트 시 네트워크 대역폭 고려
- WebSocket 연결 풀 관리 필요

### 안정성
- 클라이언트 연결 해제 시 자동 정리
- 메시지 큐잉 및 백프레셔 처리
- 장애 복구 및 재연결 로직 권장

### 확장성
- 다중 객체 지원 (여러 Husky 로봇 등)
- 메시지 타입 확장 가능한 구조
- 플러그인 아키텍처 고려