# VLM Server 실행 가이드

이 문서는 Time Travel Summarization Extension 동작을 위한 VLM 서버 실행 방법을 설명함.
VLM 서버는 **VLM Container**와 **Video Process Pipeline (NVIDIA VSS)** 두 가지 컨테이너로 구성됨.

*   **하드웨어 요구사항**:
    *   GPU: SV4000-2 서버 기준 L40 또는 A100 40GB 1대 권장 (Qwen3-VL-8B 모델 기준).

## 1. NVIDIA VSS 설치 (Clone)
NVIDIA VSS (Video Search and Summarization) 레포지토리를 클론해야 함.

*   **Repository**: `https://github.com/NVIDIA-AI-Blueprints/video-search-and-summarization.git`
*   **주의사항**:
    *   라이센스 이슈 방지를 위해 **2차 배포(Fork 포함) 금지**.
    *   로컬(서버)에서 오직 **Time Travel Summarization 실행 용도로만 사용**할 것. (Git Push 금지)
*   **역할**:
    *   VSS는 본래 Video Summarization, Q&A 등을 제공하는 Agent Blueprint임.
    *   본 프로젝트에서는 **`via-server` (비디오 청킹 및 디코딩 기능)** 만을 차용하여 비디오 처리 파이프라인으로 사용함.

## 2. 실행 방법
사용할 VLM 종류(오픈소스 모델 vs 상용 API)에 따라 실행 방식과 경로가 다름.

| 구분 | 오픈소스 VLM (Local) | 상용 VLM (API) |
| :--- | :--- | :--- |
| **실행 경로** | `deploy/docker/remote_llm_deployment/` | `deploy/docker/remote_vlm_deployment/` |
| **VLM 실행 여부** | VLM 컨테이너 별도 실행 **필요** | VLM 컨테이너 실행 **불필요** |
| **특이사항** | 환경변수(`.env`) 및 `compose.yaml` 설정 필요 | API Key 설정 및 `compose.yaml` 설정 필요 |

---

### 2.1. 오픈소스 VLM 사용 시
**NVIDIA 제공 모델** 혹은 **OpenAI API 호환 VLM**을 사용할 수 있음.
VLM 컨테이너와 VSS 컨테이너를 각각 실행해야 함.

#### 2.1.1. VLM Container 실행 (ex. Qwen3-VL-8B)
vLLM 기반으로 Qwen3-VL-8B 모델을 실행함. (SV4000-2 등 GPU 서버에서 실행)

```bash
docker run -d \
  --name qwen3-vl-8b \
  --gpus '"device=2"' \
  --network host \
  --ipc=host \
  --shm-size=16g \
  -v /home/netai/wonjune/models/Qwen3-VL-8B-Instruct:/models/Qwen3-VL-8B-Instruct:ro \
  vllm/vllm-openai:latest \
    --model /models/Qwen3-VL-8B-Instruct \
    --served-model-name Qwen3-VL-8B-Instruct \
    --tensor-parallel-size 1 \
    --max-model-len 8192 \
    --max-num-seqs 256 \
    --max-num-batched-tokens 8192 \
    --media-io-kwargs '{"video": {"num_frames": -1}}' \
    --host 0.0.0.0 \
    --port 38011
```
*   `--gpus`: 사용할 GPU 번호 지정 (예: `device=2`).
*   `-v`: 모델 파일 경로 마운트 (`/로컬/모델/경로:/컨테이너/모델/경로:ro`). 기존 VSS 코드를 수정하여 마운트 필요.
*   `--port`: VSS가 사용할 포트 번호 지정 (예: `38011`).

#### 2.1.2. VSS 환경 설정
1.  **경로 이동**: `video-search-and-summarization/deploy/docker/remote_llm_deployment/`로 이동.
2.  **환경변수 설정**:
    *   기존 `.env` 파일 삭제 후, `remote_llm_deployment_env.env` 파일을 `.env`로 이름 변경.
    *   `.env` 파일 내 `NVIDIA_API_KEY` 입력 (필수, [발급 링크](https://build.nvidia.com/explore/discover)).
    *   `NGC_API_KEY`는 필수 아님.
    *   (선택) 청크 당 프레임 수 설정: `export VLM_DEFAULT_NUM_FRAMES_PER_CHUNK=20` (참고: [설정 문서](https://docs.nvidia.com/vss/latest/content/vss_configuration.html#vlm-default-number-of-frames-per-chunk))

#### 2.1.3. `compose.yaml` 수정
`compose.yaml` 파일을 열어 다음 내용을 수정해야 함.

1.  **Volume 마운트 추가**: 소스 코드 수정 사항 반영을 위해 로컬 소스 경로를 마운트함 (`services/via-server/volumes`).
    ```yaml
    volumes:
      - /home/netai/wonjune/video-search-and-summarization/src/vss-engine/src/vlm_pipeline:/opt/nvidia/via/via-engine/vlm_pipeline
    ```
2.  **Environment 추가**: VLM 컨테이너 엔드포인트 전달을 위함 (`services/via-server/environment`).
    ```yaml
    environment:
      VIA_VLM_ENDPOINT: "${VIA_VLM_ENDPOINT:-}"
    ```
3.  **Depends_on 전부 비활성화**: 불필요한 서비스(DB 등) 실행 방지 (`services/via-server/depends_on`).
    ```yaml
    # depends_on:
      # milvus-standalone:
      #   condition: service_healthy
      # graph-db:
      #   condition: service_started
      # arango-db:
      #   condition: service_started
      # minio:
      #   condition: service_started
    ```

#### 2.1.4. 파이프라인 버그 수정 (코드 패치)
기존 코드의 "청크 생성 중단" 버그 해결을 위해 파일을 수정해야 함.
*   **대상 파일**: `/video-search-and-summarization/src/vss-engine/src/vlm_pipeline/video_file_frame_getter.py`
*   **수정 내용**: 3328라인 근처 `pipeline.set_state(Gst.State.PAUSED)` **앞에** 아래 코드 추가.

```python
pipeline.set_state(Gst.State.READY)      # 추가
pipeline.get_state(Gst.CLOCK_TIME_NONE)  # 추가

pipeline.set_state(Gst.State.PAUSED)     # 기존 코드 (이 앞에 추가)
pipeline.get_state(Gst.CLOCK_TIME_NONE)  # 기존 코드
```

#### 2.1.5. 실행
```bash
docker compose up via-server
```
이제 VLM 서버(VLM 모델 + VSS 파이프라인) 사용 준비가 완료됨.

---

### 2.2. 상용 VLM API 사용 시 (ChatGPT 등)
OpenAI API 표준을 따르는 상용 서비스를 사용할 경우, VLM 컨테이너 없이 VSS 파이프라인만 실행하면 됨.

#### 2.2.1. 환경 설정
1.  **경로 이동**: `video-search-and-summarization/deploy/docker/remote_vlm_deployment/`로 이동.
2.  **환경변수 설정**: `remote_vlm_deployment_env.env`를 `.env`로 변경.

#### 2.2.2. `compose.yaml` 수정
오픈소스 VLM 설정과 유사하지만, `VIA_VLM_ENDPOINT` 설정이 필요 없음.

1.  **Volume 마운트 추가**: 소스 코드 수정 반영용 (`services/via-server/volumes`).
    ```yaml
    volumes:
      - /home/netai/wonjune/video-search-and-summarization/src/vss-engine/src/vlm_pipeline:/opt/nvidia/via/via-engine/vlm_pipeline
    ```
2.  **Depends_on 비활성화**: 불필요한 서비스 주석 처리.

#### 2.2.3. 파이프라인 버그 수정 및 실행
*   **코드 패치**: **2.1.4항**과 동일하게 `video_file_frame_getter.py` 수정.
*   **실행**:
    ```bash
    docker compose up via-server
    ```

---

### 3. 참고: VLM 모델 교체 (Optional)
#### 3.1. OpenAI 호환 모델 (Qwen 등)
제공된 `run_qwen3-vl-8b.sh` 스크립트에서 모델 경로를 변경하여 실행 후, 환경변수 설정을 통해 모델 이름을 지정함. ([설정 문서](https://docs.nvidia.com/vss/latest/content/installation-vlms-docker-compose.html#))

```bash
export VIA_VLM_OPENAI_MODEL_DEPLOYMENT_NAME="Qwen3-VL-8B-Instruct"
```

#### 3.2. NVIDIA 제공 모델 (Cosmos, VILA 등)
`.env` 파일의 `model selection` 섹션에서 원하는 모델의 주석을 해제하여 사용 가능.
*   이 경우 `via-server` 실행 시 VLM 서버도 자동으로 실행됨.
*   `export NVIDIA_VISIBLE_DEVICES=`에 설정된 GPU에 VLM과 VSS가 함께 할당됨.

```bash
# 예시: Cosmos-Reason1 사용 시 주석 해제
# Set VLM to Cosmos-Reason1
# export VLM_MODEL_TO_USE=cosmos-reason1
# export MODEL_PATH=git:https://huggingface.co/nvidia/Cosmos-Reason1-7B
# export NVIDIA_VISIBLE_DEVICES=2
```

#### 3.3. 기타 커스텀 모델
OpenAI API 표준을 지원하지 않는 모델의 경우 [이전 문서](https://docs.nvidia.com/vss/latest/content/installation-vlms-docker-compose.html#other-custom-models-docker-compose)를 참조.
