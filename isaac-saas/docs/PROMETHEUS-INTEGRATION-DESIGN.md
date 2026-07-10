# 프로메테우스 메트릭 통합 설계안 (isaac-ui)

> **입력**: `METRICS.md` (클러스터 조사 + 권장 지침).
> **본 문서**: 그 위에 **① 미결정 항목 확정 ② isaac-ui 0.8 코드베이스 통합 지점 ③ 단계별 실행 계획**을 더한 실행용 설계안.
> **상태**: 설계만. 코드 미반영. 확정 후 구현은 code-server 사이드카와 동일 패턴이라 저위험.
> **범위**: 네트워크 중심 + CPU/메모리. **GPU(DCGM) 조인은 클러스터 DRA 업그레이드 이후(Phase 2)로 미룸.**

---

## 0. 요약 (TL;DR)

- 방식: **pull(어노테이션) + OpenTelemetry Collector 사이드카**. OTel Collector가 `hostmetrics:network` 스크래퍼로 수집해 **Prometheus 엔드포인트로 노출**하고, 기존 monitoring-ns Prometheus가 그대로 pull. 새 스크레이프 잡 / Operator / Service 포트 / OTLP 백엔드 추가 **전혀 불필요**. (METRICS.md의 node-exporter 안에서 수집 에이전트만 OTel로 교체 — "통일성" 목적.)
- 통합 지점은 **code-server 사이드카와 완전히 같은 자리·같은 방식** (`resources.deployment()`에 컨테이너 append + 토글 env + `deployment.yaml` 주석). → 구현이 익숙하고 회귀 위험 낮음.
- 신규 산출물은 사실상 **사이드카 컨테이너 1개 + pod 어노테이션 3종 + pod 라벨 1개(owner)** 뿐. (NetworkPolicy는 선택/후속, §1·§6 참고.)
- 인스턴스/소유자 단위 "통합 뷰"는 코드가 아니라 **PromQL 라벨 조인(`app`, `owner`) + Grafana**로 달성. 메트릭 이름은 OTel semconv(`system_network_*`).

---

## 1. 미결정 항목 확정 (METRICS.md의 열린 결정)

| 항목 | 확정 | 근거 |
|------|------|------|
| listen-address | **`0.0.0.0:9100` + Service에 9100 미추가** | loopback이면 Prometheus가 pod IP로 못 긁음. LB 노출은 절대 금지. pod IP 직접 스크레이프는 클러스터 내부 한정. |
| owner를 pod **label**로 승격 | **예 (sanitize 후)** | 프로젝트 목표가 "인스턴스(소유자) 단위" 사용량. annotation은 PromQL 라벨로 못 끌어옴 → owner 집계하려면 pod label 필수. Deployment selector는 `app`만 쓰므로 label 추가는 안전(셀렉터 불변). |
| NetworkPolicy로 9100 제한 | **선택/후속 (Phase 1.5)** — 기본 안전장치는 "Service 미노출" | 핵심 요구(외부 유출 금지)는 Service에 9100 안 넣는 것으로 이미 충족. NetworkPolicy는 *클러스터 내부* 차단까지 원할 때만. **주의: 인스턴스 pod에 ingress 정책을 걸면 8211/49100/47998/8080(기능 포트)도 함께 허용해줘야 안 깨짐** → footgun, 급하지 않으면 보류. |
| DCGM(GPU) 조인 | **Phase 2 (업그레이드 이후)** | GPU 미루기 방침. 네트워크/CPU/메모리는 GPU와 무관하게 먼저 확보. |
| pushgateway | **사용 안 함** | 상시 인스턴스엔 유령 메트릭. (METRICS.md §8) |

---

## 2. 코드 / 매니페스트 통합 설계

### 2.1 `config.py` — 토글 (code-server 패턴 재사용)

```python
# --- 인스턴스 메트릭 수집(OpenTelemetry Collector 사이드카) ---
METRICS_ENABLED    = _flag("METRICS_ENABLED", "1")
METRICS_OTEL_IMAGE = os.environ.get("METRICS_OTEL_IMAGE",
                                    "10.38.38.210/dt-saas/otel-collector-contrib:0.119.0")  # Harbor 미러
METRICS_PORT       = int(os.environ.get("METRICS_PORT", "9100"))
METRICS_INTERVAL   = os.environ.get("METRICS_INTERVAL", "15s")
```

### 2.2 `resources.py` `deployment()` — 사이드카 + 어노테이션 (code-server 블록과 나란히)

`if config.METRICS_ENABLED:` 블록으로 다음을 추가. **otel-collector는 native sidecar**(`initContainers` + `restartPolicy: Always`, readiness probe 없음)로 넣는다 — 수집기가 크래시해도 isaac에 영향 없고 pod readiness/LB 엔드포인트에서 안 빠진다. (단 native sidecar는 main보다 먼저 start하므로 이미지가 없으면 기동 지연 → Harbor 미러 전제, 아니면 `METRICS_ENABLED=0`.) **isaac-sim은 `containers` index 0 유지**(reconcile `containers/0/args` 패치).

**(a) pod 어노테이션** — `template.metadata.annotations`에 병합:
```yaml
prometheus.io/scrape: "true"
prometheus.io/port:   "9100"   # otel-collector만 가리킴 → code-server(8080)/isaac 포트는 안 긁힘
prometheus.io/path:   "/metrics"
```

**(b) pod 라벨에 owner 추가** — `template.metadata.labels`:
```python
labels = {"app": app, "group": config.GROUP}
if config.METRICS_ENABLED:
    labels["owner"] = _label_safe(owner)   # PromQL에서 sum by (owner)
```
sanitize(파드 라벨 제약: 시작/끝 영숫자, `[a-z0-9-]`, ≤63자):
```python
def _label_safe(v):
    s = re.sub(r"[^a-z0-9-]", "-", (v or "").lower()).strip("-")[:63].strip("-")
    return s or "unknown"
```

**(c) 사이드카 컨테이너** (OTel Collector, hostmetrics:network → prometheus exporter):
```yaml
# initContainers 항목으로 추가 (native sidecar)
- name: otel-collector
  restartPolicy: Always                # <- native sidecar (실패해도 isaac 무영향, readiness 미게이트)
  image: <METRICS_OTEL_IMAGE>          # otel/opentelemetry-collector-contrib (Harbor 미러)
  args: [ --config=env:OTEL_CONFIG ]   # config는 env로 주입(별도 ConfigMap/볼륨 불필요)
  env:
    - name: OTEL_CONFIG
      value: |
        receivers:
          hostmetrics:
            collection_interval: 15s
            scrapers:
              network:                 # node-exporter network 콜렉터에 대응 (netns-scoped)
        exporters:
          prometheus:
            endpoint: 0.0.0.0:9100     # Prometheus가 긁을 /metrics
        service:
          telemetry: { metrics: { level: none } }   # 콜렉터 자체 메트릭(:8888) 끔
          pipelines:
            metrics: { receivers: [hostmetrics], exporters: [prometheus] }
  ports: [ { name: metrics, containerPort: 9100 } ]
  resources:
    requests: { cpu: "50m",  memory: "64Mi" }
    limits:   { cpu: "200m", memory: "128Mi" }
  securityContext:
    runAsNonRoot: true
    runAsUser: 65534
    allowPrivilegeEscalation: false
    capabilities: { drop: ["ALL"] }
```
- **host 마운트 없음**: network 스크래퍼는 `/proc/net/*`(netns-scoped)를 읽으므로, 같은 pod(=netns 공유)면 인스턴스 인터페이스(eth0 등) 트래픽을 그대로 봄. **호스트 마운트를 붙이면 오히려 호스트 네트워크를 보게 되니 붙이지 않는다.**
- 비루트(65534) + `capabilities drop ALL`: `/proc/net/*`는 world-readable이라 특권 불필요.
- contrib 배포판 사용(코어엔 hostmetrics/prometheus 미포함). 태그 고정 + Harbor 미러.

### 2.3 `service.py` — **변경 없음**
9100을 Service에 넣지 않음 → LoadBalancer로 메트릭이 절대 안 뜸. (가장 중요한 통제)

### 2.4 `k8s/deployment.yaml` — UI env에 노브 주석 (code-server와 일관)
```yaml
            # 인스턴스 메트릭(OpenTelemetry Collector 사이드카) - 기본 on
            # - { name: METRICS_ENABLED,    value: "1" }   # "0"으로 끔
            # - { name: METRICS_OTEL_IMAGE, value: "10.38.38.210/dt-saas/otel-collector-contrib:0.119.0" }
            # - { name: METRICS_PORT,       value: "9100" }
            # - { name: METRICS_INTERVAL,   value: "15s" }
```

### 2.5 RBAC — **변경 없음**
사이드카는 자기 netns만 읽고, 스크레이프 주체는 `monitoring` ns의 Prometheus(별도 SA). isaac-ui SA 권한 불변. (METRICS.md §4)

### 2.6 (선택, Phase 1.5) NetworkPolicy
원하면 **클러스터 1회성 정책 1개**(per-instance 말고)로 `group: dt-sim` pod의 9100 ingress를 monitoring ns에서만 허용. 단 위 §1 footgun대로 기능 포트(8211/49100/47998/8080)도 함께 allow 해야 함 → `k8s/` 밖 별도 파일로 신중히. 급하지 않으면 보류 권장.

---

## 3. 인스턴스 / 소유자 단위 통합 (소비 설계)

식별 라벨: **`app="dt-sim-<name>"`** (기존 pod label), **`owner="<sanitized>"`** (신규).

```promql
# 인스턴스별 송/수신 대역폭 (WebRTC media 중심) — OTel hostmetrics:network → prometheus
# device="eth0" 필수: lo(루프백)는 파드 내부(code-server↔isaac) 트래픽이라 합계를 ~5배 부풀림
sum by (app) (rate(system_network_io_bytes_total{app=~"dt-sim-.+", device="eth0", direction="transmit"}[5m]))
sum by (app) (rate(system_network_io_bytes_total{app=~"dt-sim-.+", device="eth0", direction="receive"}[5m]))
# 소유자별 합계
sum by (owner)(rate(system_network_io_bytes_total{owner!="", device="eth0", direction="transmit"}[5m]))
# 품질 지표 (drop/error, TCP 연결 수)
rate(system_network_dropped_total{app=~"dt-sim-.+", device="eth0", direction="transmit"}[5m])
rate(system_network_errors_total {app=~"dt-sim-.+", device="eth0"}[5m])
system_network_connections{app=~"dt-sim-.+", protocol="tcp", state="established"}
```
> **루프백 주의**: 항상 `device="eth0"`로 필터. 안 그러면 lo가 합계를 ~5배 부풀림(검증: rx/tx 8.2MB→eth0만 1.4/1.6MB). UI 코드(`metrics.py`)는 `device!="lo"`로 이미 제외 중(=eth0와 동일). 메트릭 이름이 OTel semconv라 node-exporter와 다름(`node_network_*` → `system_network_*`, `direction` 속성).
>
> **못 잡는 것 / 프로토콜별 분석**: hostmetrics:network는 **인터페이스 단위(eth0/lo)×방향**까지만 줌 — 프로토콜/포트별 바이트 분리(WebRTC 미디어 UDP vs 시그널링 TCP, RTSP 등)와 TCP 재전송/RTT/지터는 **불가**. 필요하면 이 클러스터가 쓰는 **Cilium Hubble metrics**(L4 `destination_port`/`protocol`, 드롭/verdict, L7 옵션)를 켜서 같은 Prometheus로 스크레이프하는 게 정석 — **클러스터 단위 활성화**(per-instance 사이드카 변경 아님). 바이트 정밀 분리까지면 eBPF 바이트 어카운팅(ebpf_exporter류) 필요.
- **CPU/메모리 (cAdvisor, 기존)**: `container_*{pod=~"dt-sim-.+"}` — cAdvisor엔 `app`/`owner` 라벨이 없으니 pod 정규식으로 묶거나 `* on(pod) group_left(label_owner) kube_pod_labels` 로 조인. (METRICS.md §5)
- **GPU (DCGM, Phase 2)**: `DCGM_FI_DEV_*{pod=~"dt-sim-.+"}` — dcgm-exporter의 kube 매핑(pod 라벨) 확인 후 활성.

---

## 4. UI / Grafana 연계 (Phase 3, 선택)

- **UI 내장 수집 검증 패널 (구현됨, 0.9.3)**: 메인 화면 하단에 **pod별** 스크레이프 상태(`up` 1/0) + samples + 실시간 tx/rx rate 테이블. `/api/metrics/verify`(instant query, fail-soft)로 10s마다 갱신. "up=1 + samples>0 + tx/rx 흐름 = 정상 수집"을 Grafana 없이 체계적으로 검증.
- **UI 내장 Metrics 대시보드 (구현됨, 0.9.1)**: 툴바 **Metrics** 버튼 → 인스턴스별 송/수신 대역폭 차트(SVG 스파크라인) + **CSV/JSON 내보내기** + window(15m/1h/6h/24h). 백엔드 `/api/metrics`가 `query_range`로 읽고 **fail-soft**(Prometheus 미연결/무데이터면 빈 상태, UI/인스턴스 무영향). `PROMETHEUS_URL` env(기본 `prometheus-server.monitoring.svc`). 추가 RBAC 불필요(내부 HTTP).
- **Grafana(선택)**: `app`(+`owner`) 변수 대시보드로 §3 쿼리를 더 풍부하게 패널화.

---

## 5. 단계별 계획

| Phase | 내용 | GPU 의존 |
|-------|------|----------|
| **0 (준비)** | `./mirror-images.sh`로 OTel Collector(contrib)를 Harbor 미러(`oos-sim/otel-collector-contrib:0.119.0`, 태그 고정). **native sidecar라 이미지가 없으면 isaac이 안 뜨므로 필수 선행 단계**(태그 바꿀 때마다 재실행). + 인스턴스 pod에 `harbor-regcred`가 붙어 있어 Harbor pull이 인증됨(`resources.py`); oos-sim이 pull-public이 아니면 이게 없으면 401. | 무 |
| **1 (핵심)** | `config` 토글 + `deployment()` 사이드카·어노테이션·owner 라벨. 검증(§7). | **무** ← 지금 가능 |
| **1.5 (선택)** | NetworkPolicy (footgun 주의). | 무 |
| **2 (GPU)** | dcgm-exporter pod 라벨 확인 → GPU 메트릭 조인. | **업그레이드 이후** |
| **3 (선택)** | UI Details 대역폭 + Grafana 대시보드. | 무 |

---

## 6. 위험 / 주의

- 🔴 **메트릭을 LoadBalancer Service에 절대 노출 금지** — Service에 9100 미추가가 핵심 통제. (최우선)
- isaac-sim **컨테이너 index 0 불변** — reconcile의 `containers/0/args` 패치가 깨짐. 사이드카는 항상 뒤.
- netns 공유로 hostmetrics:network가 인스턴스 인터페이스를 봄 → **host 마운트 붙이면 호스트 네트워크를 보게 되니 금지**.
- owner 라벨 **charset/63자 제약** → sanitize 필수. 서로 다른 owner가 같은 sanitized 값이 될 수 있음(인지).
- 어노테이션 스크레이프는 **pod당 단일 포트** → 9100(otel-collector)만. code-server(8080)는 안 긁힘(의도대로).
- 이미지 **태그 고정**. Docker Hub/quay 직접 풀은 rate-limit → Harbor 미러. contrib 배포판 필수(hostmetrics/prometheus 포함).
- NetworkPolicy 도입 시 **기능 포트까지 allow** 안 하면 인스턴스 통신이 끊김(§1).

---

## 7. 검증 체크리스트

- [ ] Harbor 미러 이미지 pull 확인
- [ ] 새 인스턴스 생성 → `monitoring` Prometheus **Targets에 pod가 `up=1`**
- [ ] `system_network_*` 가 `app` / `owner` 라벨로 분리되는지
- [ ] `http://<LB IP>:9100` **외부 접근 불가**(미노출) 확인
- [ ] (NetPolicy 적용 시) monitoring 외 ns에서 9100 차단 + 기능 포트 정상

---

## 8. 하지 말 것 (METRICS.md §8 재확인)

- ❌ pushgateway (상시 인스턴스 → 유령 메트릭)
- ❌ ServiceMonitor/PodMonitor (이 클러스터엔 operator 없음 → 무시됨)
- ❌ metrics 포트를 LoadBalancer Service에 노출
- ❌ 사이드카를 containers index 0에 배치
