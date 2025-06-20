# 시스템 아키텍처

## 1. 아키텍처 개요

![시스템 아키텍처](images/architecture_overview.png)

NetAI UWB Real-time Tracking Extension은 실시간 UWB 데이터를 Omniverse 3D 환경으로 시각화하는 시스템입니다.

## 2. 시스템 구성 요소

### 2.1 Core Components

```
uwbrtls/
├── extension.py              # Main Extension Controller
├── config_manager.py         # Configuration Management
├── db_manager.py            # Database Operations
├── coordinate_transformer.py # Coordinate Transformations
└── kafka_consumer.py        # Message Processing
```

### 2.2 Component Responsibilities

#### Extension Controller (`extension.py`)
- Omniverse Extension 생명주기 관리
- UI 인터페이스 제공
- 시스템 상태 모니터링
- 컴포넌트 간 통신 조정

#### Configuration Manager (`config_manager.py`)
- JSON 설정 파일 관리
- 점 표기법 설정 접근
- 기본값 처리 및 검증
- 런타임 설정 변경

#### Database Manager (`db_manager.py`)
- PostgreSQL 연결 풀 관리
- 비동기 DB 작업 처리
- 트랜잭션 관리
- 데이터 무결성 보장

#### Coordinate Transformer (`coordinate_transformer.py`)
- UWB ↔ Omniverse 좌표 변환
- GPS 좌표 지원
- 캘리브레이션 포인트 처리
- 동적 매핑 파라미터 적용

#### Kafka Consumer (`kafka_consumer.py`)
- 실시간 메시지 수신
- 메시지 파싱 및 검증
- 백프레셔 처리
- 콜백 기반 이벤트 처리


## 3. 데이터베이스 스키마

![데이터베이스 스키마](images/database_schema.png)

### 3.1 Core Tables

CREATE TABLE spaces (
    id SERIAL PRIMARY KEY,
    space_name VARCHAR(255) NOT NULL,
    space_type VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### uwb_coordinate_systems
UWB 좌표계 정의 및 경계 설정
```sql
CREATE TABLE uwb_coordinate_systems (
    id SERIAL PRIMARY KEY,
    system_name VARCHAR(255) NOT NULL,
    min_x DECIMAL(10,3),
    max_x DECIMAL(10,3),
    min_y DECIMAL(10,3),
    max_y DECIMAL(10,3),
    unit VARCHAR(10) DEFAULT 'meters'
);
```

#### omniverse_coordinate_systems
Omniverse 좌표계 매개변수
```sql
CREATE TABLE omniverse_coordinate_systems (
    id SERIAL PRIMARY KEY,
    system_name VARCHAR(255) NOT NULL,
    scale_factor DECIMAL(10,6) DEFAULT 1.0,
    offset_x DECIMAL(10,3) DEFAULT 0.0,
    offset_y DECIMAL(10,3) DEFAULT 0.0,
    offset_z DECIMAL(10,3) DEFAULT 0.0,
    rotation_degrees DECIMAL(8,3) DEFAULT 0.0
);
```

#### coordinate_mappings
좌표계 간 매핑 관리
```sql
CREATE TABLE coordinate_mappings (
    id SERIAL PRIMARY KEY,
    space_id INTEGER REFERENCES spaces(id),
    uwb_coordinate_system_id INTEGER REFERENCES uwb_coordinate_systems(id),
    omniverse_coordinate_system_id INTEGER REFERENCES omniverse_coordinate_systems(id),
    mapping_name VARCHAR(255) NOT NULL,
    scale_x DECIMAL(10,6) DEFAULT 1.0,
    scale_y DECIMAL(10,6) DEFAULT 1.0,
    translate_x DECIMAL(10,3) DEFAULT 0.0,
    translate_y DECIMAL(10,3) DEFAULT 0.0,
    translate_z DECIMAL(10,3) DEFAULT 0.0,
    rotation_z DECIMAL(8,3) DEFAULT 0.0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### transformed_coordinates
실시간 변환된 좌표 저장
```sql
CREATE TABLE transformed_coordinates (
    id SERIAL PRIMARY KEY,
    tag_id VARCHAR(50) NOT NULL,
    space_id INTEGER REFERENCES spaces(id),
    uwb_x DECIMAL(10,3) NOT NULL,
    uwb_y DECIMAL(10,3) NOT NULL,
    omniverse_x DECIMAL(10,3) NOT NULL,
    omniverse_y DECIMAL(10,3) NOT NULL,
    omniverse_z DECIMAL(10,3) NOT NULL,
    coordinate_mapping_id INTEGER REFERENCES coordinate_mappings(id),
    uwb_timestamp VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### calibration_points
캘리브레이션 포인트 관리
```sql
CREATE TABLE calibration_points (
    id SERIAL PRIMARY KEY,
    coordinate_mapping_id INTEGER REFERENCES coordinate_mappings(id),
    point_name VARCHAR(255) NOT NULL,
    uwb_x DECIMAL(10,3) NOT NULL,
    uwb_y DECIMAL(10,3) NOT NULL,
    omniverse_x DECIMAL(10,3) NOT NULL,
    omniverse_y DECIMAL(10,3) NOT NULL,
    omniverse_z DECIMAL(10,3) NOT NULL,
    is_reference_point BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### uwb_tag (기존 테이블)
UWB 태그 매핑
```sql
CREATE TABLE uwb_tag (
    tag_id INTEGER PRIMARY KEY,
    nuc_id VARCHAR(255),
    description TEXT
);
```

#### uwb_timestamp_tracking (기존 테이블)
타임스탬프 추적
```sql
CREATE TABLE uwb_timestamp_tracking (
    id SERIAL PRIMARY KEY,
    tag_id VARCHAR(50) NOT NULL,
    raw_timestamp VARCHAR(255),
    omniverse_timestamp VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```


## 4. 좌표 변환 시스템

![좌표 변환](images/coordinate_transform.png)

### 4.1 변환 파이프라인

1. **입력 검증**: UWB 좌표 유효성 확인
2. **매핑 적용**: DB에서 변환 매개변수 조회
3. **기하학적 변환**: 회전, 스케일링, 평행이동
4. **결과 검증**: 변환된 좌표 범위 확인
5. **출력**: Omniverse 좌표 반환

### 4.2 변환 수식

```
// 회전 변환
x' = x * cos(θ) - y * sin(θ)
y' = x * sin(θ) + y * cos(θ)

// 스케일링 및 평행이동
omni_x = x' * scale_x + offset_x
omni_z = y' * scale_y + offset_y
omni_y = fixed_height + offset_z
```

## 5. Omniverse 위한 비동기 처리 부분분

### 56.1 연결 풀링

```python
ThreadedConnectionPool(
    minconn=1,
    maxconn=5,
    **db_config
)
```

### 5.2 비동기 처리

```python
# 메시지 처리와 DB 저장을 병렬 실행
await asyncio.gather(
    move_object_by_name(name, position),
    record_timestamp_to_db(tag_id, timestamp)
)
```


### 5.2 비동기 처리

```python
# 메시지 처리와 DB 저장을 병렬 실행
await asyncio.gather(
    move_object_by_name(name, position),
    record_timestamp_to_db(tag_id, timestamp)
)
```

### 5.3 Kafka 기반 비동기 메시지 처리

#### 비동기 Consumer 구현
```python
from aiokafka import AIOKafkaConsumer

class KafkaMessageProcessor:
    async def _consume_messages(self):
        self._consumer = AIOKafkaConsumer(
            self.topic_name,
            bootstrap_servers=self.bootstrap_servers,
            auto_offset_reset="earliest",
            group_id=self.group_id
        )
        
        await self._consumer.start()
        
        async for msg in self._consumer:
            # 메시지 처리를 별도 태스크로 실행 (논블로킹)
            asyncio.create_task(
                self._process_single_message(msg.value.decode('utf-8'))
            )
```

#### 백프레셔 처리
```python
async def _process_single_message(self, decoded_message):
    try:
        # JSON 파싱 및 검증
        message_data = json.loads(decoded_message)
        
        # 좌표 변환 및 저장 (비동기)
        omni_coords = await self.coordinate_transformer.transform_and_save(
            tag_id, uwb_x, uwb_y, raw_timestamp
        )
        
        # UI 업데이트 콜백 (논블로킹)
        if self._message_callback:
            await self._message_callback(object_name, tag_id, omni_coords)
            
    except Exception as e:
        print(f"Error processing message: {e}")
        # 메시지 처리 실패 시에도 consumer는 계속 실행
```

#### 연결 복구 메커니즘
```python
async def _consume_messages(self):
    max_retries = 5
    retry_delay = 2.0
    
    for attempt in range(max_retries):
        try:
            await self._start_kafka_consumer()
            break
        except Exception as e:
            print(f"Kafka connection failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 1.5  # 지수 백오프
```                