# Time Travel Summarization Extension

이 문서는  **Time Travel Summarization Framework**를 구현한 **Time_travel_Summarization** Extension의 사용 설명서입니다.
본 프레임워크는 Dream-AI_Plus_Twin.usd를 기반으로 구현되었으며 시계열 궤적 데이터를 활용하여 디지털트윈의 과거 상태를 복원하고, 이를 기반으로 **Event-based Summarization** (현재 '충돌' 이벤트 지원)을 생성합니다.

> **Extension ID:** `netai.timetravel_dreamai`
> *(Extension의 초기 개발 명칭인 `netai.timetravel_dreamai`가 유지됨.)*

## 📝 Note: 용어 및 구조 정의

*   **Time Travel의 정의**:
    *   **본 문서:** 시간의 흐름에 따라 객체의 위치 상태를 복원하고 재생하는 기능.
    *   **공식적(교수님) 관점:** 단순 복원을 넘어선 통합적인 시공간 분석 기능의 통칭. 본 프레임워크는 이를 지원하는 도구입니다.

*   **익스텐션 구조**:
    *   익스텐션은 다양한 모듈로 구성되며 `extension.py`를 통해 통합 초기화.
    *   모듈: Time Travel, View overlay, Vlm Client, Event Post-Processing

## Extension 설치 가이드

### 1. USD Composer 설치

*   Omniverse kit-app-template 레포(https://github.com/NVIDIA-Omniverse/kit-app-template.git)를 clone 한다. 
*   레포지토리의 **Prerequisits and Environment Setup** 을 따라 **USD COmposer** 설치한다.
*   **새로운 어플리케이션을 생성하는 과정(.\repo.bat template new)에서 `? Do you want to add application layers? [ENTER to confirm]` 에서 `Yes`  를 선택한 뒤 `[omni_default_streaming]: Omniverse Kit App Streaming (Default)` 를 체크하여 설치한다.** (선택하지 않을 시 뷰포트 로드가 불가한 에러 발생)
*   USD Composer를 빌드한다. (`.\repo.bat build` for window, `.\repo.sh build` for linux)

### 2. Extenson 설치
*   kit-app-template/source/extension 경로에 Time Travel Summarization 디렉토리를 복사한다. 

### 3. USD Composer 실행
*   USD Composer를 실행한다. (`.\repo.bat launch`)
*   Developer/Extension의 검색창에 `netai` 검색
*   `NVIDIA`의 `Sample` 항목에서 `TIME_TRAVEL_SUMMARIZATION` 활성화


---

## 🚀 사용 가이드 (Workflow) 및 기능 설명

프레임워크의 작동 순서에 따른 단계별 사용법.

### 0. VLM 서버 실행

VLM 서버를 실행합니다. 
서버에서 VLM container와 Video process pipeline (NVIDIA VSS) 를 각자 실행.  
GPU는 SV4000-2 기준으로 l40 또는 A100 40GB 한대로 충분.

자세한 내용은 `./VLM_server` 디렉토리 README.md에서 확인

---
### 1. 궤적 데이터 생성

디지털트윈 환경에서 객체의 움직임을 표현할 시계열 궤적 데이터를 생성.

```bash
python utils/trajectory_data_generater_XAI_Studio.py
```
파일 내부에서 데이터 생성 조건 변경

---
### 2. Config 설정

`netai/timetravel_dreamai/config.json` (또는 관련 설정 파일)에서 다음 항목을 설정.
*   **data_path**: 생성된 궤적 데이터(.csv) 경로 지정
*   **astronaut_usd**: Time Travel 객체로 사용할 USD 파일 경로 지정 (현재는 Astronaut USD 파일 사용 중)
*   **auto_generate**: `true` 이면 Extension 초기화시 time travel 객체 자동 생성 (data_path의 objectID 수 만큼 생성)
---
### 3. Extension Initialization

USD Composer 실행 후 `Extension` 창에서 **Time Travel Summarization**을 찾아 활성화. (Extension ID: `netai.timetravel_dreamai`)
*   실행 시 Time Travel, View Overlay, VLM Client, Event Post Processing 등 모든 모듈의 UI Window가 초기화됩니다.
---
### 4. Time Travel

**기능:** 시계열 데이터를 기반으로 과거 상태를 재현하고 탐색.
*   **자동 객체 생성**: 데이터 내 ID 개수만큼 객체(Astronaut) 생성 및 매핑.
*   **Dataset Range**: 시계열 데이터의 시작 timestamp와 끝 timestamp 표시.
*   **Go**: 특정 Timestamp 시점으로 즉시 이동.
*   **Stage Time**: 현재 재현된 디지털트윈의 시간 표시.
*   **Play/Speed**: 시간 흐름에 따른 재생 및 속도 조절.
*   **Timeline slider**: 타임바를 통한 선형적 시점 조절.

> **구현 파일:** `core.py`, `window.py`
---
### 5. View Overlay

VLM이 이벤트 발생 시간과 연루된 객체를 특정할 수 있도록 하기 위한 visual prompting 과정

**기능:** 복원된 디지털트윈 장면 위에 객체 정보(ID)와 현재 시간(Timestamp)을 오버레이함. 

**사용법:**  
*   timestamp, objectIDs overlay 체크박스 선택

> **구현 파일:**
> *   `modules/view_overlay.py`, `modules/overlay_control.py`
---
### 6. Visual Abstraction & Temporal Acceleration (Optional)

VLM의 추론 성능을 극대화하기 위해 디지털트윈 환경을 조정하는 단계.

#### Visual Abstraction (시각적 단순화)
*   **목적:** 불필요한 시각 정보를 줄여 VLM이 객체 상호작용에 집중하도록 함.
*   **방법:** Omniverse Stage 창의 '눈(Eye)' 아이콘을 통해 Prim 그룹(Furniture, Equipment 등)을 비활성화.
*   **단계 예시:** Full Digital Twin → Simplified (Equipment 제거) → Abstract (Equiptment + A_Exterior 제거, View Overlay만 유지)

#### Temporal Acceleration (시간 가속)
*   **목적:** VLM에 전달되는 동영상의 재생 속도를 가속하여(영상 길이를 단축하여) VLM 처리 속도 향상.
*   **경험적 성능:** '충돌' 이벤트 검출 시 **3배속** 영상까지는 추론 성능 저하가 없었음. (이벤트 특성에 따라 조절 필요)
*   시간 가속된 동영상 생성 방법은 "7. 동영상 추출" 에서 설명.
---
### 7. 동영상 추출 (Movie Capture)

**Movie Capture Extension** (내장 기능)을 사용하여 VLM 서버로 전송할 영상을 생성. 
*현재 동영상 추출 단계가 파이프라인의 주요 병목구간.*
*영상 전달을 스트리밍 방식으로 확장 필요함.(NVIDIA VSS가 RTSP를 지원함)*

#### 📸 캡쳐 가이드
Movie Capture의 고정된 캡쳐 FPS 특성상, 원하는 재생 속도의 동영상을 얻기 위해 **Time Travel 재생 속도 조절**이 필요함.

*   **설정 값**:
    *   **Camera prim name**: `BEV_cam` 
    *   **Frame rate**: 30 FPS
    *   **Capture range(Seconds) End**: 생성할 영상의 길이(초) 선택
    *   **Resolution**: 532 x 280 (빠른 추론속도와 reshape 과정에서의 정보 손실 방지를 위함. 변경 가능.)
    *   **Output Path**: extension 경로 내부의 video 폴더 (ex. C:\Users\wonjune\workspace\kit-app-template\source\extensions\netai.timetravel_dreamai\netai\timetravel_dreamai\video)
    *   **Output Name**: `video_n.mp4` 형식 필수 (NVIDIA VSS 요구사항)
    

#### 재생 속도 설정 공식
Movie Capture는 기본적으로 10 FPS 로 캡쳐를 진행함.  
*   Frame rate 와 Cumstom Range end (second) 를 곱한 수 만큼의 이미지를 10FPS 속도로 캡쳐한 뒤 동영상 인코딩.  
예를 들어, 30FPS, 60초 Capture range 설정을 하면, 30x60 = 1800 장의 이미지를 10FPS로 촬영함.  
따라서 1800/10 = 180초가 소요. 그러므로 Time Travel 재생 속도를 0.33x 로 설정하여 3분동안 시뮬레이션(재생)이 진행되도록 조절해야 60초 길이의 동영상을 생성할 수 있음.  
1분(60초) 분량의 데이터를 캡쳐할 때 권장 설정은 다음과 같음.

| 목표 영상 속도 | 결과 영상 길이 | Custom Range End | **Time Travel Play Speed** | 설정 이유 |
| :--- | :--- | :--- | :--- | :--- |
| **1배속 (정속)** | 60초 | 60 | **0.33x** | Capture가 약 3분동안 진행되므로, 재생 속도를 1/3로 늦춰야 1배속 영상 생성됨 |
| **3배속 (가속)** | 20초 | 20 | **1.0x** | 정속 재생으로 캡쳐 시, 결과적으로 약 3배 빠른 영상(Temporal Acceleration)이 생성됨 |
---
### 8. VLM Client

생성된 영상을 VLM 서버(NVIDIA VSS)로 전송하고 추론 결과를 받음.  
VLM 서버에 동영상을 upload하고, 추론 요청(generate)하는 두 과정을 거침  

**기능:**
*   **Upload**: 생성한 `video_n.mp4` VLM 서버에 업로드.
*   **Delete**: VLM 서버에 업로드한 영상 삭제.(삭제 안하고 다른 영상 업로드해도 작동하긴 함)
*   **Generate**: VLM 모델 추론 요청.
*   **Settings**:
    *   Model: VLM 서버에서 실행 중인 모델 선택.
    *   Preset: Visual abtraction 정도에 따라 프롬프트 유형 선택 (`twin_view`: 입력된 동영상을 디지털트윈 BEV 영상으로 묘사, `simple_view`: 단순 도형의 움직임으로 묘사).
    *   Overlap: 동영상 청크의 겹침 정도(초) 설정. 1초 단위.
*   **결과**: `vlm_outputs/` 경로에 JSON 형태로 저장됨.

**사용법:**
*   Upload -> Settings -> Genearte

> **구현 파일:** `modules/vlm_client_core.py`, `modules/vlm_client_window.py`, `utils/VSS_client`
*   VLM 서버의 동영상 처리 파이프라인(VSS)과 통신하는 기능은 `utils/VSS_client` 에 구현
*   `vlm_client_core.py`는 `VSS_client`를 활용하여 익스텐션의 구조와 경로에 맞게 작업을 지시하는 역할
    *   경로 설정, 프롬프트 정의, 업로드된 비디오 ID 상태관리 등
    *   VLM에 전달되는 동영상 청크의 길이는 `modules/vlm_client_core.py`의 `default_chunk_duration` 에서 설정 가능. (청크에 포함되는 frame 개수는 VLM server에서 설정)
---
### 9. Event Post Processing

VLM의 output을 Time Travel 모듈에서 재생 가능한 형태(Event List)로 변환.  
core.py 에서 event_post_processing_core.py 를 import하여 데이터를 가공(core.py 의 in-memory data를 활용해야하기 때문).

**기능:**
*   **Input**: `vlm_outputs/` 내의 JSON 파일명.
*   **Process Events** (core.py 에서 진행됨):
    1.  JSON 파싱 및 정제 (중간단계 결과물: `*_intermediate.jsonl`)
    2.  이벤트 발생 시점의 객체 3D 좌표 추출 (`core.py` 의 in-memory 데이터 참조)
    3.  최종 결과물 `*_eventlist.jsonl` 생성 (경로: `event_list/`)

**사용법:**
*   Input JSON File에 파일 이름 복붙 -> Process Evetns 버튼

> **구현 파일:** `core.py`, `modules/event_post_processing_core.py`, `modules/event_post_processing_window.py`
---
### 10. Event-based Summarization Playback

최종 Event list를 활용하여 사건 중심 요약을 생성.

**사용법:**
*  Time Travel Window의 **Event based summary mode** 체크.
*  **Play**: 이벤트 리스트를 순회하며, 이벤트 발생 구간만 자동 재생.
    *   재생 길이: `core.py`의 `_event_playback_duration` 설정값 (기본 1초).
    *   화면 이동: 이벤트 발생 시공간(위치+시간)으로 Viewport 자동 이동.
*  **Next Event** (Pause 상태일때): 버튼 클릭 시 다음 이벤트 발생 직전 시점으로 점프.

---
