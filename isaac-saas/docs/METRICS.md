# 인스턴스별 메트릭 수집 설계 지침 (구현 전 가이드)

> 상태: **설계 문서. 아직 코드에 반영하지 않음.** 인스턴스마다 메트릭 수집기를 붙여
> 클러스터 Prometheus로 네트워크 사용량 중심 + GPU/CPU/메모리 주요 데이터를
> **인스턴스(소유자) 단위**로 보내기 위한 권장 지침이다.

---

## 1. 클러스터 사실 (조사 결과)

| 항목 | 사실 | 함의 |
|------|------|------|
| Prometheus 종류 | **prometheus-community Helm 차트** (`monitoring` ns: server/alertmanager/kube-state-metrics/node-exporter/pushgateway) | **prometheus-operator 아님** |
| CRD | `monitoring.coreos.com` 없음 | **ServiceMonitor/PodMonitor 못 씀** |
| 스크레이프 디스커버리 | `kubernetes-pods` 잡이 **pod 어노테이션 기반** (`prometheus.io/scrape|port|path|scheme`) | pod에 어노테이션만 붙이면 **pod IP로 직접 스크레이프**(Service 불필요) |
| pod label 매핑 | `kubernetes-pods` 잡이 `__meta_kubernetes_pod_label_*` 를 라벨로 매핑 | 우리 pod의 `app=dt-sim-<name>` 가 **메트릭 라벨로 자동 부여** → 인스턴스별 쿼리 가능 |
| 컨테이너 네트워크 | `kubernetes-nodes-cadvisor` 잡 가동 → `container_network_*` 이미 수집 | rx/tx bytes·packets·drops·errors는 **이미 pod 단위로 존재** |
| GPU | `nvidia-dcgm-exporter` (gpu-operator) 가동 | `DCGM_FI_DEV_*` 이미 수집 (pod 매핑은 §5 확인) |
| pushgateway | 존재하지만 **상시 인스턴스엔 비권장** | pod 종료 후 메트릭 잔존 → 유령 데이터. **쓰지 않는다** |
| CNI | Cilium | `monitoring` ns의 Prometheus가 pod IP로 직접 도달 가능 |

**결론:** push 아닌 **pull(어노테이션) 방식**이 정답. 새 스크레이프 잡/Operator/Service 포트
추가가 전혀 필요 없다 — pod에 어노테이션 + 사이드카만 추가하면 된다.

---

## 2. 무엇을 어떻게 수집하나 (역할 분담)

| 데이터 | 출처 | 신규 작업 |
|--------|------|-----------|
| **네트워크 (상세)** | **node-exporter 사이드카** (인스턴스 pod의 netns) — netdev/netstat/sockstat | ✅ 신규 (§3) |
| 네트워크 (기본 rx/tx) | cAdvisor (기존) | 없음 — 보강용으로 병행 |
| GPU 사용률/메모리/인코더 | DCGM exporter (기존) | pod 라벨 조인만 (§5) |
| CPU/메모리 | cAdvisor + kube-state-metrics (기존) | 없음 — 쿼리/대시보드만 (§5) |

> 핵심 신규 작업은 **node-exporter 사이드카 + pod 어노테이션** 둘뿐. GPU/CPU/메모리는
> 이미 수집되므로 "전부 인스턴스 단위 통합"은 **PromQL 라벨 조인 + 대시보드**로 달성한다.

---

## 3. node-exporter 사이드카 (네트워크 전용)

`resources.py`의 `deployment()` 빌더에서, 지금 code-server 사이드카를 추가하는 패턴과
**동일한 방식**으로 컨테이너를 하나 더 append 한다. (isaac-sim은 반드시 index 0 유지 —
reconcile이 `containers/0/args`를 패치하므로. 사이드카는 뒤에 붙인다.)

### 3.1 컨테이너 스펙 (권장값)

```yaml
- name: net-exporter
  image: 10.38.38.210/dt-saas/node-exporter:1.8     # Harbor 미러 권장 (rate-limit 회피)
                                                     # 원본: quay.io/prometheus/node-exporter:v1.8.2
  args:
    - --web.listen-address=127.0.0.1:9100   # ↓ 보안 주: 노출 범위 결정 후 조정
    - --path.rootfs=/host                    # 사용 안 하면 생략 가능
    - --collector.disable-defaults           # 필요한 콜렉터만 켠다 (네트워크 중심)
    - --collector.netdev                     # per-interface rx/tx bytes·packets·errs·drop
    - --collector.netstat                    # /proc/net/netstat,snmp (TCP 재전송 등)
    - --collector.sockstat                   # 소켓/연결 수 (TCP/UDP in-use)
  ports:
    - { name: metrics, containerPort: 9100 }
  resources:
    requests: { cpu: "20m",  memory: "32Mi" }
    limits:   { cpu: "100m", memory: "64Mi" }
  securityContext:
    runAsNonRoot: true
    runAsUser: 65534
    allowPrivilegeEscalation: false
    capabilities: { drop: ["ALL"] }
```

- **netns 공유:** 사이드카는 같은 pod라 isaac-sim 컨테이너와 **네트워크 네임스페이스를
  공유** → `--collector.netdev`가 인스턴스가 실제 쓰는 인터페이스(eth0 등)의 트래픽을
  그대로 본다. 별도 설정 불필요.
- **`--path.rootfs`/host 마운트는 네트워크 메트릭엔 불필요** → 마운트 안 하는 게 안전.
  위 args에서 `--path.rootfs` 줄은 빼도 된다(네트워크 콜렉터만 쓸 경우).
- **listen-address 결정 필요(§3.3).**

### 3.2 pod 어노테이션 (스크레이프 트리거)

`deployment()`의 `template.metadata.annotations` (또는 pod template metadata)에 추가:

```yaml
prometheus.io/scrape: "true"
prometheus.io/port:   "9100"
prometheus.io/path:   "/metrics"
```

이것만 있으면 `kubernetes-pods` 잡이 pod IP:9100/metrics 를 자동 스크레이프하고,
pod label `app=dt-sim-<name>` 이 메트릭 라벨로 따라붙는다.

### 3.3 ⚠️ 결정 필요 — metrics 포트 노출 범위

인스턴스 Service는 `type: LoadBalancer`(외부 공개)다. **메트릭은 외부로 절대 노출 금지.**
두 가지 안전한 선택:

1. **`--web.listen-address=0.0.0.0:9100` + Service에는 9100 포트를 추가하지 않음**
   (권장). Prometheus는 pod IP로 직접 긁으므로 클러스터 내부에서만 접근. Service에
   9100을 안 넣으면 LB로는 안 뜬다. Cilium NetworkPolicy로 9100을 `monitoring` ns만
   허용하면 더 견고.
2. `127.0.0.1:9100`은 **사이드카 스크레이프엔 부적합**(Prometheus가 pod IP로 접근하므로
   loopback이면 못 긁음). 쓰지 말 것.

→ **권장: `0.0.0.0:9100`, Service 포트 미추가, (선택) NetworkPolicy로 monitoring ns만 허용.**

### 3.4 토글 (code-server 패턴 재사용)

`config.py`에 환경변수로 on/off 노출 권장 (기본 on):

```
METRICS_ENABLED        = _flag("METRICS_ENABLED", "1")
METRICS_EXPORTER_IMAGE = os.environ.get("METRICS_EXPORTER_IMAGE", "<harbor>/oos-sim/node-exporter:1.8")
METRICS_PORT           = int(os.environ.get("METRICS_PORT", "9100"))
```

`deployment()`에서 `if config.METRICS_ENABLED:` 블록으로 컨테이너 + 어노테이션 추가.
`deployment.yaml`의 UI env에 주석으로 노브를 적어두면 code-server와 일관.

---

## 4. RBAC / 매니페스트 영향

- **추가 RBAC 불필요.** 사이드카는 자기 netns만 읽고, 스크레이프 주체는 `monitoring` ns의
  Prometheus(별도 SA). isaac-ui SA 권한 변화 없음.
- **Service 변경 불필요**(§3.3 권장안 기준).
- (선택) **NetworkPolicy** 1개 추가로 9100을 monitoring ns에만 개방 — `k8s/` 밖,
  인스턴스 템플릿 차원에서 관리할지 결정 필요.

---

## 5. 인스턴스 단위 "전부 통합" — PromQL 라벨 조인

모든 소스가 공통적으로 `pod` 또는 `app` 라벨을 가지므로 인스턴스 단위로 묶을 수 있다.
인스턴스 식별 라벨은 **`app="dt-sim-<name>"`** (pod label, 모든 소스에 존재하거나 조인 가능).

### 네트워크 (사이드카, 핵심)
```promql
# 인스턴스별 송신 대역폭 (bytes/s) — WebRTC media 중심
sum by (app) (rate(node_network_transmit_bytes_total{app=~"dt-sim-.+"}[5m]))
sum by (app) (rate(node_network_receive_bytes_total {app=~"dt-sim-.+"}[5m]))
# 드롭/에러, 재전송, 소켓 수
rate(node_network_transmit_drop_total{app=~"dt-sim-.+"}[5m])
rate(node_netstat_Tcp_RetransSegs{app=~"dt-sim-.+"}[5m])
node_sockstat_TCP_inuse{app=~"dt-sim-.+"}
```

### 네트워크 보강 (cAdvisor, 기존)
```promql
sum by (pod) (rate(container_network_transmit_bytes_total{namespace="oos-sim",pod=~"dt-sim-.+"}[5m]))
```
> cAdvisor는 `app` label이 없고 `pod`만 있다. 대시보드에서 `pod` 정규식으로 묶거나,
> `* on(pod) group_left(...) kube_pod_labels` 로 조인.

### GPU (DCGM, 기존)
```promql
# DCGM exporter가 pod 라벨을 달고 있는지 먼저 확인:
#   DCGM_FI_DEV_GPU_UTIL{namespace="oos-sim"}  결과에 pod= 라벨이 있는가?
# gpu-operator 기본값은 kube 매핑 on → pod/namespace/container 라벨 존재.
DCGM_FI_DEV_GPU_UTIL{namespace="oos-sim", pod=~"dt-sim-.+"}
DCGM_FI_DEV_FB_USED {namespace="oos-sim", pod=~"dt-sim-.+"}
DCGM_FI_DEV_ENC_UTIL{namespace="oos-sim", pod=~"dt-sim-.+"}   # WebRTC 인코더 사용률
```
> pod 라벨이 없다면 gpu-operator의 dcgm-exporter에 kube 매핑(`--kubernetes=true`)이
> 켜졌는지 확인 필요(읽기 조사 항목). 없으면 GPU↔인스턴스 조인이 불가하니 이때만
> 별도 조치.

### CPU / 메모리 (cAdvisor, 기존)
```promql
sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="oos-sim",pod=~"dt-sim-.+"}[5m]))
sum by (pod) (container_memory_working_set_bytes{namespace="oos-sim",pod=~"dt-sim-.+"})
```

### 소유자 단위 집계 (선택)
인스턴스 → 소유자 매핑은 Deployment annotation(`dt-saas.wks/owner`)에 있다. Prometheus
라벨로 끌어오려면 pod **label** 에 owner를 넣어야 한다(현재는 annotation). 소유자 단위
집계가 필요하면 `resources.py`에서 pod template label에 `owner=<sanitized>` 추가를
검토(라벨 제약: 63자/charset). — **이건 별도 결정 항목**.

---

## 6. UI 연계 (선택, 후속)

- 인스턴스 Details 드로어에 "현재 송/수신 대역폭" 같은 요약을 보이려면, UI가
  `prometheus-server.monitoring.svc:80/api/v1/query` 로 instant query 하면 된다
  (읽기 전용, 추가 RBAC 불필요 — 클러스터 내부 HTTP).
- Grafana(`monitoring`)에 `app` 을 변수로 한 인스턴스 대시보드 1개를 만들면 §5 쿼리를
  그대로 패널화 가능. **권장: Grafana 대시보드로 통합 뷰 제공.**

---

## 7. 구현 체크리스트 (코드 반영 시)

- [ ] node-exporter 이미지를 **Harbor에 미러**(`oos-sim/node-exporter:1.8`) — rate-limit/재현성
- [ ] `config.py`: `METRICS_ENABLED / METRICS_EXPORTER_IMAGE / METRICS_PORT` 추가
- [ ] `resources.py deployment()`: `if METRICS_ENABLED` → 사이드카 컨테이너 append(§3.1) +
      pod 어노테이션 3종(§3.2). **isaac-sim index 0 불변 유지**
- [ ] listen-address `0.0.0.0:9100`, Service 포트 **미추가**(§3.3)
- [ ] (선택) 9100을 monitoring ns만 허용하는 NetworkPolicy
- [ ] DCGM pod 라벨 유무 확인 → 없으면 gpu-operator 매핑 점검
- [ ] (선택) owner를 pod label로 승격할지 결정
- [ ] Grafana 인스턴스 대시보드(`app` 변수) 작성
- [ ] 검증: 새 인스턴스 생성 → `monitoring` Prometheus의 Targets에 pod가 `up=1` 로
      뜨고, §5 쿼리가 `app` 라벨로 분리되는지 확인

---

## 8. 하지 말 것

- ❌ pushgateway 사용 (상시 인스턴스엔 부적합, 유령 메트릭)
- ❌ ServiceMonitor/PodMonitor 작성 (이 클러스터엔 operator 없음 → 무시됨)
- ❌ metrics 포트를 LoadBalancer Service에 노출 (외부 유출)
- ❌ 사이드카를 containers index 0 에 넣기 (reconcile의 args 패치가 깨짐)
