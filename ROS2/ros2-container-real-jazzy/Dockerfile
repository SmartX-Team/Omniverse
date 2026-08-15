# 베이스 이미지: ROS 2 Jazzy (Ubuntu Noble 24.04)
# Jazzy 포팅 노트: Clearpath cmd_vel은 TwistStamped (teleop publish_stamped_twist=true)
# 빌더 스테이지 - 시스템 기본 설정
FROM ros:jazzy-ros-base-noble AS base-builder

# APT 패키지 설치 시 상호작용 프롬프트 비활성화
ARG DEBIAN_FRONTEND=noninteractive

# RUN 명령어에 사용할 기본 쉘을 bash로 설정
SHELL ["/bin/bash", "-c"]

# 시스템 업데이트 (별도 레이어)
RUN apt-get update

# 기본 개발 도구 설치 (별도 레이어)
RUN apt-get install -y --no-install-recommends \
        git \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

# ROS 2 개발 도구 설치 (별도 레이어)
FROM base-builder AS ros2-builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-colcon-common-extensions \
        ros-jazzy-rmw-fastrtps-cpp \
    && rm -rf /var/lib/apt/lists/*

# Ouster 워크스페이스 준비 단계
FROM ros2-builder AS ouster-workspace

ENV OUSTER_WS_ROOT=/root/ouster_ws
ENV OUSTER_WS_SRC=${OUSTER_WS_ROOT}/src

# Ouster 소스 클론
RUN mkdir -p ${OUSTER_WS_SRC}
WORKDIR ${OUSTER_WS_SRC}
# 버전 핀 (2026-08): ros2 브랜치 HEAD는 SDK 0.16.x — FW 3.2 전용 WINDOW 필드를
# 핵심 스캔 경로에서 접근해 구펌웨어(2.5.3, OS-1-32-U1)에서 std::out_of_range abort.
# 릴리스 태그 ros2-v0.13.2 (WINDOW 도입 이전, FW 2.x 호환)로 고정.
RUN git clone --branch ros2-v0.13.2 --recurse-submodules https://github.com/ouster-lidar/ouster-ros.git

# Ouster 의존성 설치 및 빌드 단계
FROM ouster-workspace AS ouster-built

WORKDIR ${OUSTER_WS_ROOT}

# Ouster 의존성 설치
RUN . /opt/ros/jazzy/setup.bash && \
    apt-get update && \
    rosdep install --from-paths src --ignore-src -r -y --rosdistro jazzy && \
    rm -rf /var/lib/apt/lists/*

# Ouster 빌드
RUN . /opt/ros/jazzy/setup.bash && \
    colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release

# ============================================================================
# Runtime Stage - 기본 설정
# ============================================================================
FROM ros:jazzy-ros-base-noble AS runtime-base

ARG DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

# 환경 변수 설정
ENV RMW_IMPLEMENTATION=rmw_fastrtps_cpp
ENV SDL_VIDEODRIVER=x11

# 시스템 업데이트
RUN apt-get update

# 기본 도구 설치 (별도 레이어)
FROM runtime-base AS runtime-tools

RUN apt-get install -y --no-install-recommends \
        curl \
        gnupg \
        lsb-release \
        apt-transport-https \
        software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 및 기본 라이브러리 설치 (별도 레이어)
FROM runtime-tools AS runtime-python

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-pip \
        python3-venv \
        python3-yaml \
        python3-opencv \
        python3-pygame \
    && rm -rf /var/lib/apt/lists/*

# SDL 및 그래픽 라이브러리 설치 (별도 레이어)
FROM runtime-python AS runtime-graphics

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libsdl2-2.0-0 \
        libsdl2-image-2.0-0 \
        libsdl2-mixer-2.0-0 \
        libsdl2-ttf-2.0-0 \
        libgl1 \
        libglx-mesa0 \
        libx11-6 \
        libxext6 \
        libxrandr2 \
        libxcursor1 \
    && rm -rf /var/lib/apt/lists/*

# ROS 패키지 설치 (별도 레이어)
FROM runtime-graphics AS runtime-ros

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ros-jazzy-rviz2 \
        ros-jazzy-rmw-fastrtps-cpp \
        ros-jazzy-cv-bridge \
        libpcap-dev \
        # === Nav2 + SLAM  ===
        ros-jazzy-nav2-bringup \
        ros-jazzy-slam-toolbox \
        ros-jazzy-robot-localization \
        ros-jazzy-dwb-plugins \
        # === PS5 DualSense 텔레옵 (신규) ===
        ros-jazzy-joy \
        ros-jazzy-teleop-twist-joy \
        # sensors launch가 참조하는 relay (기존 이미지엔 누락돼 있던 잠재 버그 수정)
        ros-jazzy-topic-tools \
    && rm -rf /var/lib/apt/lists/*

# Intel RealSense — Intel apt 저장소 제거 (GPG 키/네트워크 말썽 원인)
# librealsense2는 ROS apt 저장소의 vendor 패키지(ros-jazzy-librealsense2)로 대체.
# realsense2-camera 설치 시 의존성으로 자동 포함되므로 이 스테이지는 패스스루.
FROM runtime-ros AS runtime-realsense

# Clearpath 저장소 설정 (별도 레이어)
FROM runtime-realsense AS runtime-clearpath-setup

RUN echo "Setting up Clearpath Robotics APT repository..." && \
    mkdir -p /usr/share/keyrings && \
    curl -fsSL https://packages.clearpathrobotics.com/public.key | gpg --dearmor -o /usr/share/keyrings/clearpath-archive-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/clearpath-archive-keyring.gpg] \
    https://packages.clearpathrobotics.com/stable/ubuntu noble main" > /etc/apt/sources.list.d/clearpath-robotics.list

# Clearpath 패키지 설치 (별도 레이어)
FROM runtime-clearpath-setup AS runtime-clearpath

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ros-jazzy-clearpath-robot \
        ros-jazzy-clearpath-simulator \
        ros-jazzy-clearpath-config \
        ros-jazzy-clearpath-generator-common \
        ros-jazzy-robot-upstart \
        ros-jazzy-xacro \
    && rm -rf /var/lib/apt/lists/*

# RealSense ROS 패키지 설치 (별도 레이어)
FROM runtime-clearpath AS runtime-realsense-ros

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ros-jazzy-librealsense2 \
        ros-jazzy-realsense2-camera \
        ros-jazzy-realsense2-description \
    && rm -rf /var/lib/apt/lists/*

# 설정 파일 복사 단계
FROM runtime-realsense-ros AS runtime-configs

# 디렉토리 생성 및 설정 파일 복사
RUN mkdir -p /configs /etc/clearpath

COPY /src/husky_isaac_bringup/config/robot.yaml /etc/clearpath/robot.yaml
COPY /src/husky_isaac_bringup/config/driver_params.yaml /configs/ouster_driver_params.yaml
COPY /src/husky_isaac_bringup/config/ouster_param.yaml /configs/ouster_param.yaml
COPY /src/husky_isaac_bringup/config/ds5_teleop.yaml /configs/ds5_teleop.yaml

# DDS 프로파일 (entrypoint 기본 경로) — 원본에선 누락돼 있던 부분 보강
RUN mkdir -p /etc/fastdds
COPY /src/husky_isaac_bringup/config/fastdds_force_udp.xml /etc/fastdds/fastdds_force_udp.xml

# Clearpath 설정 생성 단계
FROM runtime-configs AS runtime-clearpath-gen

RUN echo "Generating Clearpath platform scripts and configurations..." && \
    . /opt/ros/jazzy/setup.bash && \
    echo "Executing generate_bash..." && \
    ros2 run clearpath_generator_common generate_bash --setup_path /etc/clearpath && \
    echo "Executing generate_description..." && \
    ros2 run clearpath_generator_common generate_description --setup_path /etc/clearpath && \
    echo "Executing generate_param..." && \
    ros2 run clearpath_generator_robot generate_param --setup_path /etc/clearpath && \
    echo "Executing generate_launch..." && \
    ros2 run clearpath_generator_robot generate_launch --setup_path /etc/clearpath && \
    echo "Clearpath generation completed." && \
    # odom->base_link TF 활성화 (2026-08): Clearpath 기본값 False는 자체 localization
    # 스택 전제 — 우리는 EKF 없이 diff-drive 휠 오도메트리 TF를 직접 사용 (SLAM 요구사항)
    sed -i 's/enable_odom_tf: False/enable_odom_tf: True/' /etc/clearpath/platform/config/control.yaml && \
    grep -n "enable_odom_tf" /etc/clearpath/platform/config/control.yaml

# Python 라이브러리 설치 (별도 레이어)
FROM runtime-clearpath-gen AS runtime-python-libs

RUN pip3 install --no-cache-dir --break-system-packages kafka-python requests

# 빌드된 워크스페이스 복사 단계
FROM runtime-python-libs AS runtime-workspaces

# Ouster 워크스페이스 복사
ENV OUSTER_WS_ROOT=/root/ouster_ws
COPY --from=ouster-built ${OUSTER_WS_ROOT} ${OUSTER_WS_ROOT}

# 최종 단계 - 애플리케이션 파일 복사
FROM runtime-workspaces AS final

RUN mkdir -p /root/app_ws

COPY src/ /root/app_ws/src/

#독립 스크립트 복사
COPY standalone_scripts/ /root/standalone_scripts/

# PS5 텔레옵 런치 (신규)
COPY src/husky_isaac_bringup/launch/ds5_teleop.launch.py /root/ds5_teleop.launch.py


WORKDIR /root

# bash 접속 시 ROS Humble 환경 자동 source
RUN echo 'source /opt/ros/jazzy/setup.bash' >> /root/.bashrc

# SLAM/Nav2 세션 스크립트 (사용자 수동 실행: docker exec -it husky /root/start_slam_nav.sh)
COPY start_slam_nav.sh /root/start_slam_nav.sh
COPY teleop_supervisor.sh /root/teleop_supervisor.sh
RUN chmod +x /root/start_slam_nav.sh /root/teleop_supervisor.sh

# 호스트 udev 규칙 (참고용으로 이미지에도 동봉 — 실제 설치는 호스트에서)
COPY deploy/99-dualsense-js.rules /root/deploy/99-dualsense-js.rules

COPY entrypoint.sh /ros_entrypoint.sh
RUN chmod +x /ros_entrypoint.sh

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]