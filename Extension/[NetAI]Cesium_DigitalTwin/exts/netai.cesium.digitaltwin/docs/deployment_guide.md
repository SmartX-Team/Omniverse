# 🏗️ NetAI Cesium Digital Twin - Development Guide

## 📋 아키텍처 설계 철학

### 🎯 **왜 이런 구조로 설계했나?**

이 Extension은 **실시간 Digital Twin 시스템**이라는 복잡한 요구사항을 만족하기 위해 **모듈화된 아키텍처**로 설계되었습니다.
해당 문서는 클로드4 가 다른 세션에 넘기라고 만든 문서임 

## 🏛️ 프로젝트 구조 분석

```
[NetAI]Cesium_DigitalTwin/
├── exts/netai.cesium.digitaltwin/     # Extension 패키지
│   ├── config/extension.toml          # Extension 메타데이터
│   ├── netai/cesium/digitaltwin/      # 메인 코드베이스
│   │   ├── core/                      # 핵심 비즈니스 로직
│   │   ├── websocket/                 # 통신 레이어
│   │   ├── ui/                        # 사용자 인터페이스
│   │   ├── utils/                     # 공통 유틸리티
│   │   └── extension.py               # Entry Point
│   └── tests/                         # 테스트 코드
```

## 🎨 **설계 원칙**

### **1. 관심사의 분리 (Separation of Concerns)**
```
🎯 목적: 각 모듈이 하나의 책임만 가지도록 설계

core/coordinate_reader.py    → Cesium Globe Anchor 좌표 읽기만 담당
core/object_tracker.py       → 객체 추적 로직만 담당  
core/selection_handler.py    → Omniverse 객체 선택만 담당
websocket/client.py          → WebSocket 통신만 담당
utils/config.py              → 설정 관리만 담당
utils/logger.py              → 로깅만 담당
```

**💡 장점:**
- 각 모듈을 독립적으로 개발/테스트 가능
- 버그 발생 시 원인 파악이 용이
- 새로운 기능 추가 시 기존 코드에 미치는 영향 최소화

### **2. 느슨한 결합 (Loose Coupling)**
```python
# ❌ 강한 결합 (지양)
class ObjectTracker:
    def __init__(self):
        self.websocket = WebSocketClient()  # 직접 의존

# ✅ 느슨한 결합 (지향)  
class ObjectTracker:
    def add_coordinate_callback(self, callback):
        self.callbacks.append(callback)  # 콜백을 통한 통신
```

**💡 장점:**
- 모듈 간 의존성 최소화
- 테스트 시 Mock 객체 사용 용이
- 런타임에 동적 연결 가능

### **3. 확장 가능한 아키텍처**
```
📦 현재 구조로 쉽게 추가 가능한 기능들:

netai/cesium/digitaltwin/
├── sensors/                 # 센서 데이터 처리
│   ├── lidar_handler.py
│   └── camera_handler.py
├── ai/                      # AI/ML 기능
│   ├── path_planning.py
│   └── object_detection.py
└── protocols/               # 다른 통신 프로토콜
    ├── mqtt_client.py
    └── ros2_bridge.py
```

## 🔧 **핵심 모듈별 설계 의도**

### **📍 Core 모듈 (`core/`)**

#### **`coordinate_reader.py`**
```python
🎯 설계 의도: Cesium Globe Anchor API의 복잡성을 추상화

- Globe Anchor API 직접 사용의 복잡함 해결
- 에러 처리 및 좌표 유효성 검증 통합
- 메타데이터 수집 로직 포함
- 배치 처리로 성능 최적화
```

#### **`object_tracker.py`**
```python
🎯 설계 의도: 실시간 추적의 복잡한 상태 관리

- 비동기 추적 루프 관리
- 좌표 변화 감지 알고리즘
- 통계 정보 수집 및 모니터링
- 콜백 시스템으로 확장성 확보
```

#### **`selection_handler.py`**
```python
🎯 설계 의도: Omniverse Selection API의 스레드 안전성 보장

- 메인 스레드에서만 Selection API 호출
- 웹 UI로부터의 선택 명령 처리
- 다중 객체 선택 지원
- 카메라 포커스 등 부가 기능 준비
```

### **🌐 WebSocket 모듈 (`websocket/`)**

#### **`client.py`**
```python
🎯 설계 의도: 견고한 실시간 통신 보장

- 자동 재연결 메커니즘 (최대 5회 시도)
- 별도 스레드에서 비동기 처리
- 메시지 큐잉 및 통계 수집
- 콜백 기반 이벤트 처리
```

**왜 별도 스레드?**
- Omniverse UI는 메인 스레드에서 실행
- WebSocket 블로킹 없이 UI 반응성 유지
- 네트워크 지연이 3D 렌더링에 영향 없음

### **🛠️ Utils 모듈 (`utils/`)**

#### **`config.py`**
```python
🎯 설계 의도: Omniverse 설정 시스템과 통합

- extension.toml 설정을 런타임에서 읽기/쓰기
- 타입 안전성 및 기본값 보장
- 설정 변경 시 자동 적용
```

#### **`logger.py`**
```python
🎯 설계 의도: 통합된 로깅 시스템

- Omniverse 로그 시스템 활용
- 모듈별 구분된 로그 메시지
- WebSocket/좌표 전용 디버그 함수
- 성능에 영향 없는 조건부 로깅
```

## 🏗️ **Extension 구조의 특별한 점**

### **1. `exts/` 폴더 구조**
```
🎯 목적: Omniverse Extension Manager 호환성

exts/netai.cesium.digitaltwin/  ← Extension Manager가 인식하는 구조
├── config/extension.toml       ← Extension 메타데이터
└── netai/cesium/digitaltwin/   ← Python 패키지 구조
```

**왜 이렇게?**
- Omniverse Extension Manager 표준 구조
- 다른 Extension과의 네임스페이스 충돌 방지
- 버전 관리 및 의존성 해결 지원

### **2. 깊은 패키지 구조 (`netai.cesium.digitaltwin`)**
```python
🎯 목적: 네임스페이스 충돌 방지 및 조직적 관리

netai/           ← 회사/조직 네임스페이스
└── cesium/      ← 기술 스택 네임스페이스  
    └── digitaltwin/  ← 프로젝트 네임스페이스
```

**장점:**
- 다른 Extension과 이름 충돌 없음
- 향후 `netai.cesium.mapping`, `netai.isaac.robotics` 등 확장 용이
- Python import 시 명확한 출처 표시

## 🔄 **데이터 흐름 설계**

### **실시간 좌표 전송 플로우**
```
1. ObjectTracker (1초마다)
   ↓ tracking_loop()
2. CoordinateReader
   ↓ get_multiple_coordinates()  
3. Globe Anchor API
   ↓ 좌표 데이터
4. ObjectTracker 콜백
   ↓ _on_coordinate_update()
5. WebSocketClient
   ↓ send_coordinate_update()
6. 백엔드 서버 → 웹 지도
```

### **웹 선택 명령 플로우**
```
1. 웹 지도 (마커 클릭)
   ↓ WebSocket 메시지
2. WebSocketClient
   ↓ _on_websocket_message()
3. Extension 메인 콜백
   ↓ _on_websocket_message()
4. SelectionHandler
   ↓ handle_web_selection_request()
5. Omniverse Selection API
   ↓ 메인 스레드에서 실행
6. 객체 선택 완료
```

## 🧪 **테스트 가능한 설계**

### **모듈별 독립 테스트**
```python
# 각 모듈은 독립적으로 테스트 가능
tests/
├── test_coordinate_reader.py   # Mock Cesium API
├── test_object_tracker.py      # Mock CoordinateReader  
└── test_websocket_client.py    # Mock 서버
```

### **의존성 주입 패턴**
```python
# 테스트 시 Mock 객체 주입 가능
class ObjectTracker:
    def __init__(self, coordinate_reader=None):
        self.coordinate_reader = coordinate_reader or CoordinateReader()
```

## 🚀 **성능 최적화 설계**

### **1. 배치 처리**
```python
# 개별 좌표 읽기 (비효율)
for prim_path in objects:
    coords = get_coordinates(prim_path)  # N번 API 호출

# 배치 좌표 읽기 (효율)  
coords_batch = get_multiple_coordinates(objects)  # 1번 API 호출
```

### **2. 변화 감지**
```python
# 좌표가 실제로 변했을 때만 전송
if self._coordinates_changed(old_coords, new_coords):
    send_update()  # 불필요한 네트워크 트래픽 방지
```

### **3. 비동기 처리**
```python
# UI 블로킹 없는 백그라운드 처리
async def tracking_loop():        # 별도 스레드
    while running:
        await update_coordinates()
        await asyncio.sleep(1.0)
```

## 🎯 **확장성 고려사항**

### **새로운 센서 추가**
```python
# 새로운 센서 모듈 추가 시
netai/cesium/digitaltwin/sensors/
├── lidar_reader.py
├── camera_reader.py  
└── imu_reader.py

# ObjectTracker에 센서 콜백만 추가
tracker.add_sensor_callback(lidar_callback)
```

### **다른 통신 프로토콜 지원**
```python
# MQTT, ROS2 등 추가 시
netai/cesium/digitaltwin/protocols/
├── mqtt_client.py
├── ros2_bridge.py
└── tcp_server.py

# Extension에서 선택적 활성화
if config.get_mqtt_enabled():
    mqtt_client.start()
```