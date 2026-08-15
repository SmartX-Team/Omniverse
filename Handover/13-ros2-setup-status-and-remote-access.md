# 13 - ROS2 세팅 현황 및 원격접속 방법 (2026-08-15 개정)

- 작성자: 송인용
- 개정일: 2026-08-15 (초판 2026-01 → 전면 개정)
- 목적: 연구실 Husky A200 운용을 위해 구축된 **ROS2 Jazzy 기반 실행환경(도커 포함)**의 "현재 세팅 현황"과, 해당 환경에 **원격접속 방법**을 정리한다.
- 범위: Humble → Jazzy 마이그레이션 이후의 "현재 세팅 현황" 요약 + 새로운 머신 세팅가이드 + 트러블슈팅 이력
- 실제 사용방법은 14번 문서부터 읽어볼것

---

## 13.1 ROS2 업그레이드 및 운영 구조 개요(현황 요약)

### 작업 배경
- 기존 세팅된 ROS2 환경은 Isaac Sim 4.5 연동을 전제로 한 ROS2 Humble 기반이었음
- 이후 Isaac Sim 6.0 으로 전환하면서 4.5 시절 가상 로봇 연동 코드(IsaacSim-ros_workspaces, isaac_sim 모드)는 대대적으로 업데이트가 필요했음
- 현재 배포된 컨테이너는 실제 현실 A200 운용에 집중한 이미지를 ROS2 Jazzy(Ubuntu 24.04 Noble) 로 마이그레이션한 버전임
- Isaac Sim 6.0 대응 가상 로봇 연동은 추후 재작업 예정

---

## 13.2 ROS2 세팅 현황

### 13.2.1 ROS2 배포판/실행 방식
- ROS2 배포판: **Jazzy Jalisco**
- 실행 방식: Docker 기반 (베이스 이미지 `ros:jazzy-ros-base-noble`)
- 호스트 OS/아키텍처: 우분투 22 이상 (컨테이너가 Noble 이므로 호스트 배포판 무관, 커널 5.15+ 권장 — DualSense hid_playstation 드라이버 때문)
- 컨테이너 이름/이미지 이름: 하단의 도커 허브내 주소 및 명령어 참조

### 13.2.2 관련 레포/이미지 위치

- **ROS2 폴더(메인 진입점)**
  - Repo: `SmartX-Team/Omniverse`
  - Path: `ROS2/`
  - Link: https://github.com/SmartX-Team/Omniverse/tree/main/ROS2

- 관련 코드 위치(Repo/폴더):
  - `Omniverse/ROS2/ros2-container-real/` *(신규 — 실물 전용, 이번 개정의 대상)*
    - Jazzy 기반 실물 A200 운용 컨테이너 (베이스 + Ouster + RealSense + PS5 텔레옵 + SLAM/Nav2)
  - `Omniverse/ROS2/ros2-container/` *(구버전 — Humble/Isaac 4.5 시절, 참고용으로만 유지)*
  - `Omniverse/Extension/[NetAI]GIST_Husky_IsaacSim_ROS/`
    - Isaac Sim **4.5** Husky Extension 코드 — 6.0 에서는 동작하지 않음, 재작성 필요

- Docker 이미지 Repo/Registry:
  - 사전 빌드 이미지: `docker.io/ttyy441/ros2-container-real` *(신규 레포)*
  - 예시 태그:
    - **`1.1-jazzy` (Current, 2026-08-15)**: Jazzy 전환 + 현실 로봇 대상 테스트 완료한 버전
    - 구 이미지 `ttyy441/ros2-container:0.6.0` 해당 컨테이너는 가급적 사용하지 말 것 


### 13.2.3 주의사항 및 제한 사항(중요)
- 신규 머신을 ROS 용으로 추가 장착하는 것은 가능하나, **Husky 배터리 출력으로 구동할 장비는 mini-NUC 시리즈 또는 Jetson 급**을 권장. 고성능 PC를 장착할 경우 **필요 전류(A) 및 소비전력(W)을 사전에 산정**한 뒤 장착하거나 **외부 전원 공급**을 사용

- ROS2 머신은 전원이 들어온다고 자동부팅 안될 수 있으니 **NUC 전원 버튼 수동으로 누르는거 꼭 확인**. 단 컨테이너는 `--restart unless-stopped` 로 등록해두면 부팅 후 자동 기동됨 (13.4.3) ; 다만 현재는 직접 세팅해두지는 않음
- Ouster LiDAR IP는 처음 납풉받은 그대로 **192.168.131.20**. NUC 이더넷 포트(현재 머신 기준 eno1)에 **192.168.131.1/24 고정 할당 필요** — DHCP 로 두면 안 됨! netplan 설정까지 해야 재부팅에도 유지됨 (13.6 트러블슈팅 #4 참고)
- **cmd_vel 이 TwistStamped 로 바뀜 (Jazzy Clearpath)**: `ros2 topic pub` 으로 수동 주행 테스트할 때 Twist 로 쏘면 조용히 무시됨. 반드시 `geometry_msgs/msg/TwistStamped` 사용
- ROS_DOMAIN_ID: 현재 robot.yaml 이 **domain 0** 으로 생성함. docker run 에 `-e ROS_DOMAIN_ID=20` 등을 줘도 **Clearpath setup.bash 가 0 으로 덮어쓰니** 헷갈리지 말 것 — env 를 아예 안 주고 0 으로 통일해 쓰는 중

---

## 13.3 원격접속 방법(접속 경로)

> DHCP 나 환경이 지남에 따라 원격 주소가 변경되어 있을 수 있으니, 새로 작업하는 사람이 한번쯤은 모니터 연결후 직접 할당받은 IP 사용 권장

이번 개정 검증은 mini-nuc (NUC10i7FNH) + 신규 이미지 1.1-jazzy 기준으로 수행하였음 (2026-08-15)

### 13.3.1 접속 대상 주요 정보
- NUC-ROS2 (ROS2 Jazzy Docker 실행 머신)
  - 위치/보관: AI 대학원 mini-nuc (NUC10i7FNH)
  - 네트워크 연결: 무선 (wlp0s20f3) — **유선 포트(eno1)는 Ouster 전용으로 192.168.131.1 고정이므로 인터넷/SSH 용도로 사용 불가임**

---

## 13.4 접속후 ROS2 가동 확인
해당 내용은 만약 현재 장착한 mini-nuc 대신 새로운 PC를 Husky UGV 제어용으로 세팅할때 필요한 내용임
기존 머신으로 작업시에는 해당 절 안내하는 내용이 전부 세팅되어 있으니 14번 문서로 넘어가면됨
### 13.4.1 사전 준비 (신규 머신 1회 설정)


**(1) Ouster 용 이더넷 고정 IP (netplan)**
```bash
# /etc/netplan/50-cloud-init.yaml (또는 eno1 항목이 있는 파일) 의 eno1 부분을:
#   eno1:
#     dhcp4: false
#     addresses: [192.168.131.1/24]
sudo netplan apply
sudo chmod 600 /etc/netplan/*.yaml   # 권한 경고 방지
ip -br addr show eno1                # UP 192.168.131.1/24 확인 (센서 전원 켜진 상태)
```
※ nmcli 로만 바꾸면 netplan 이 원복시킴 — **반드시 netplan 파일 자체도 같이 수정**

**(2) Ouster UDP 수신 버퍼 (패킷 드랍 방지)**
```bash
echo -e "net.core.rmem_max=26214400\nnet.core.rmem_default=26214400" | sudo tee /etc/sysctl.d/90-ouster.conf
sudo sysctl --system
```


## 13.5 트러블슈팅 이력 (Humble→Jazzy 마이그레이션에서 잡은 것들)

이번 개정 작업(2026-08-14~15)에서 실제로 밟은 지뢰들. **혼자 트러블슈팅하다가 한번씩 만날 수 있으니 아래 내용 AI한테 복붙해서 넣어서 알려달라고하셈 ㅇ**

| # | 증상 | 원인 | 해결 (v1.1 반영 여부) |
|---|---|---|---|
| 1 | os_driver 가 몇 초 만에 exit -6 (abort), `Field 'WINDOW' not found` | ouster-ros ros2 브랜치 HEAD(SDK 0.16.x)가 FW 3.2 전용 필드를 접근 — 보유 센서는 OS1-32 **FW 2.5.3** | 드라이버를 **릴리스 태그 ros2-v0.13.2 로 핀** (반영됨). 센서 펌웨어를 3.x 로 올리면 최신 드라이버 사용 가능하나 미검증 |
| 2 | 노드는 도는데 `ros2 topic list` 가 텅 빔 | docker run 의 ROS_DOMAIN_ID=20 을 **Clearpath setup.bash 가 0 으로 덮어씀** → CLI(20) 와 노드(0) 도메인 불일치 | env 를 주지 않고 0 으로 통일 (운영 방침) |
| 3 | SDL 기반 joy 노드: 장치는 열리는데(`Opened joystick`) /joy 이벤트가 전혀 안 흐름 | 헤드리스 컨테이너에서 SDL 이벤트 루프 먹통 | **joy_linux(커널 js 직독) 로 전환** (반영됨) |
| 4 | eno1 에 192.168.131.1 을 nmcli 로 줘도 재부팅/재연결 시 사라짐 | 이 프로필이 **netplan 생성물**이라 netplan 이 dhcp4:true 로 계속 원복 | **netplan 파일 자체 수정** (dhcp4:false + addresses) 후 `netplan apply` |
| 5 | Nav2 controller: `No critics defined for FollowPath` | 노드를 네임스페이스(/a200_0000)로 띄우면 params yaml 키가 FQN 과 안 맞아 **통째로 무시**됨 | launch 에서 **RewrittenYaml(root_key=ns)** 적용 (반영됨) |
| 6 | costmap: `frame "odom" does not exist` | Clearpath Jazzy 기본값 `enable_odom_tf: False` (자체 localization 전제) → odom→base_link TF 발행자 없음 | 이미지 빌드 시 control.yaml 을 **True 로 패치** (반영됨) |
| 7 | slam_toolbox 가 살아있는데 scan 구독도 map 발행도 안 함 | **Jazzy 에서 lifecycle 노드로 전환됨** — configure/activate 없이는 UNCONFIGURED 로 잠듦 | launch 에 **재시도 루프 기반 lifecycle 활성화** 내장 (반영됨, 로그 마커 "slam_toolbox lifecycle up") |
| 8 | /a200_0000/map 이 안 보임 (SLAM 은 정상) | slam_toolbox 가 map 토픽을 **절대경로 /map** 으로 발행해 네임스페이스 탈출 | launch 리매핑으로 /a200_0000/map 에 가둠 (반영됨) |
| 9 | controller_manager Overrun WARN 폭주 | A200 의 pl2303 USB-시리얼이 느려 20 Hz 제어 루프가 밀림 | **정상 동작** (주행 가능). 거슬리면 제어 주기 하향 검토 — 미반영 |
| 10 | 패드 재접속 후 /joy 침묵 (장치 노드는 존재) | 재열거로 js 노드가 새로 생기는데 joy 노드가 **죽은 옛 핸들**을 쥠. BT "반죽음"(연결 표시만 되고 입력 리포트 없음) 세션도 관측됨 | **teleop_supervisor**: 본체 js 노드를 /proc 에서 추적 + inode 변화 감지 시 joy_linux 자동 재기동 (반영됨). 반죽음 상태 자체는 패드 재접속(PS 버튼) 시 재열거되며 함께 복구됨. 상시 운용은 USB-C 직결이 가장 확실 |
| 11 | RealSense 노드가 파라미터에서 죽거나 /camera/color/image 가 빈 토픽 | realsense-ros 4.5x 에서 `depth_module.profile` → `depth_module.depth_profile` 개명 + 토픽이 `/camera/realsense_camera/...` 아래로 발행되어 옛 리매핑 키가 미스매치 | 파라미터명/리매핑 FQN 교정 (**v1.1** 반영) |
| 12 | Ouster: 붙었다가 죽음 / 스캔은 오는데 SLAM 이 드랍 | (a) `mtp_dest`(멀티캐스트 전용)가 유니캐스트 구성에 섞임 (b) 센서 내부 클럭 스탬프가 시스템 시각 TF 와 어긋남 | (a) mtp_dest 제거 (b) `timestamp_mode: TIME_FROM_ROS_TIME` (반영됨) |

---

