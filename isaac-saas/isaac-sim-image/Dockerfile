# =====================================================================
#  Isaac Sim 6.0 Container (dt-saas)  —  5.1 세트의 6.0 업데이트판
#
#  5.1 대비 변경:
#   - 베이스: nvcr.io/nvidia/isaac-sim:6.0.0 (multi-arch, Python 3.12,
#     베이스 OS는 5.1과 동일하게 Ubuntu 24.04 → ROS Jazzy 블록 유지)
#   - 6.0 베이스는 rootless 사용자(uid 1234, HOME=/isaac-sim)로 실행됨.
#     기존 랩 운영(확장 symlink, git pull, k8s UI의 OMNI_KIT_ALLOW_ROOT=1)과의
#     호환을 위해 이 이미지는 의도적으로 root 유지. entrypoint 는 $HOME 기준
#     경로를 쓰므로 rootless 로 돌려도 동작한다 (docker run -u 1234:1234).
#   - 실험 스크립트 기본 내장: /opt/experiment/{wander.py,set_4k.py}
#     (5.1 때는 research/image/ 오버레이로 뒤에 덧댔던 것 — 6.0은 기본 포함,
#      별도 -exp 오버레이 재푸쉬 불필요)
#   - WebRTC 런처: 6.0 은 runheadless.sh 가 native livestream. 구 5.1 경로
#     (/isaac-sim/isaac-sim.streaming.sh)로 호출돼도 entrypoint 가 자동 매핑.
# =====================================================================
FROM nvcr.io/nvidia/isaac-sim:6.0.0

# 6.0 베이스는 non-root 로 시작 → 빌드(apt 등)는 root 로 수행
USER root

# 비대화형 설치 + 타임존
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Seoul
RUN apt-get update && apt-get install -y tzdata && \
    ln -fs /usr/share/zoneinfo/${TZ} /etc/localtime && \
    dpkg-reconfigure --frontend noninteractive tzdata

# 기본 패키지 (24.04 noble 패키지명 — 5.1 과 동일)
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gpg git vim xvfb x11vnc x11-utils \
    mesa-utils libgl1 libglx-mesa0 libgl1-mesa-dri libegl1 libegl-mesa0 libglu1-mesa \
    curl gnupg lsb-release jq \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ROS2 Jazzy 설치 (6.0 베이스 = Ubuntu 24.04 Noble, 5.1 과 동일)
#  - Isaac Sim 6.0 브리지도 system_default 라 24.04 에선 Jazzy 를 자동 로드
#    (공식 지원: Humble/22.04, Jazzy/24.04 — Jazzy 권장)
RUN apt-get update && apt-get install -y software-properties-common && add-apt-repository universe -y && \
    apt-get update && curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | tee /etc/apt/sources.list.d/ros2.list > /dev/null && \
    apt-get update && apt-get install -y --no-install-recommends \
    ros-jazzy-ros-base \
    python3-rosdep \
    build-essential python3-colcon-common-extensions \
    ros-jazzy-vision-msgs ros-jazzy-ackermann-msgs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# libbrotli 충돌 회피 (PPA 제거)
RUN rm -f /etc/apt/sources.list.d/*sury*.list && apt-get update

RUN rosdep init || echo "rosdep already initialized" && rosdep update

# VSCode (개발 편의 — 불필요하면 이 블록 삭제)
RUN wget -qO- https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > packages.microsoft.gpg \
    && install -D -o root -g root -m 644 packages.microsoft.gpg /etc/apt/keyrings/packages.microsoft.gpg \
    && sh -c 'echo "deb [arch=amd64,arm64,armhf signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main" > /etc/apt/sources.list.d/vscode.list' \
    && rm -f packages.microsoft.gpg \
    && apt-get update && apt-get install -y --no-install-recommends code \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# =====================================================================
#  Omniverse Extensions
#  - 주소는 build.env 의 EXT_REPO_URLS 로 주입 (여러 개면 공백 구분)
#  - 비워두면 clone 생략 → 런타임에 EXT_SRC_DIR 로 볼륨 마운트하면 됨
#  - 경로는 베이스 이미지 관례 유지 (/opt/oos_omniverse_extensions)
# =====================================================================
ARG EXT_REPO_URLS=""
ARG EXT_SRC_DIR="/opt/oos_omniverse_extensions"
ENV EXT_SRC_DIR="${EXT_SRC_DIR}"
RUN mkdir -p "${EXT_SRC_DIR}" && \
    if [ -n "${EXT_REPO_URLS}" ]; then \
        for url in ${EXT_REPO_URLS}; do \
            name=$(basename "${url}" .git); \
            echo "[build] cloning ${url} -> ${EXT_SRC_DIR}/${name}"; \
            git clone "${url}" "${EXT_SRC_DIR}/${name}" || echo "[build] clone failed: ${url}"; \
        done; \
    else \
        echo "[build] EXT_REPO_URLS 비어있음 — build.env 채우거나 런타임에 ${EXT_SRC_DIR} 마운트"; \
    fi

# =====================================================================
#  Isaac Sim ROS Workspaces (Jazzy) — 선택 사항 (5.1 과 동일)
#  - 6.0 도 Jazzy 브리지 내장 → 표준 토픽 pub/sub 은 외부 워크스페이스 불필요
#  - 커스텀 메시지/외부 노드/MoveIt 예제용 → build.env 에 BUILD_ROS_WS=1
# =====================================================================
ARG BUILD_ROS_WS=0
ENV ROS_WS_DIR="/root/isaac_sim_ros_ws"
RUN if [ "${BUILD_ROS_WS}" = "1" ]; then \
        set -e; \
        echo "[build] BUILD_ROS_WS=1 -> 외부 jazzy_ws 빌드"; \
        mkdir -p ${ROS_WS_DIR}/src && cd ${ROS_WS_DIR}/src && \
        git clone https://github.com/isaac-sim/IsaacSim-ros_workspaces.git && \
        cd IsaacSim-ros_workspaces/jazzy_ws && \
        apt-get update && apt-get install -y --no-install-recommends libfreetype6-dev && \
        . /opt/ros/jazzy/setup.sh && \
        (rosdep init 2>/dev/null || true) && rosdep update && \
        rosdep install -i --from-paths src --rosdistro jazzy -y \
            --skip-keys="isaac_sim_visual_slam isaac_ros_apriltag topic_based_ros2_control" && \
        . /opt/ros/jazzy/setup.sh && colcon build --symlink-install ; \
    else \
        echo "[build] BUILD_ROS_WS=0 -> 외부 워크스페이스 생략 (내장 Jazzy 브리지 사용)"; \
    fi

# =====================================================================
#  실험 스크립트 기본 내장 (KCI 측정, 구 5.1-exp1 오버레이 대체)
#  Isaac Script Editor 에서:  exec(open("/opt/experiment/wander.py").read())
# =====================================================================
COPY experiment/wander.py /opt/experiment/wander.py
COPY experiment/set_4k.py /opt/experiment/set_4k.py
# stage open/close -> isaac-ui 리포터 (REPORT_URL env 있을 때만 활성, entrypoint 참조)
COPY experiment/stage_report.py /opt/experiment/stage_report.py

COPY entrypoint.sh /isaac-sim/entrypoint.sh
RUN chmod +x /isaac-sim/entrypoint.sh

# 환경 변수
ENV NVIDIA_DRIVER_CAPABILITIES=all
ENV NVIDIA_VISIBLE_DEVICES=all
ENV ACCEPT_EULA=Y

WORKDIR /isaac-sim
ENTRYPOINT ["/isaac-sim/entrypoint.sh"]
CMD []
