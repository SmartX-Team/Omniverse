# 베이스 이미지: ROS 2 Humble (Ubuntu Jammy)
# 빌더 스테이지 - 시스템 기본 설정
FROM ros:humble-ros-base-jammy AS base-builder

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
        ros-humble-rmw-fastrtps-cpp \
    && rm -rf /var/lib/apt/lists/*

# IsaacSim 워크스페이스 준비 단계
FROM ros2-builder AS isaac-workspace

ENV HOST_LIKE_WORKSPACE_ROOT=/root/isaac_sim_ros_ws
ENV ROS2_WS_SRC=${HOST_LIKE_WORKSPACE_ROOT}/src

# 워크스페이스 디렉토리 생성 및 소스 클론
RUN mkdir -p ${ROS2_WS_SRC}
WORKDIR ${ROS2_WS_SRC}
RUN git clone https://github.com/NVIDIA-Omniverse/IsaacSim-ros_workspaces.git

# IsaacSim 의존성 설치 단계
FROM isaac-workspace AS isaac-deps

WORKDIR ${ROS2_WS_SRC}/IsaacSim-ros_workspaces/humble_ws

# rosdep 초기화 및 의존성 설치 (별도 레이어)
RUN . /opt/ros/humble/setup.bash && \
    apt-get update && \
    rosdep init || true && \
    rosdep update && \
    rm -rf /var/lib/apt/lists/*

RUN . /opt/ros/humble/setup.bash && \
    apt-get update && \
    rosdep install -i --from-paths src --rosdistro humble -y --skip-keys "isaac_sim_μέρος_python_venv rviz_ogre_vendor" && \
    rm -rf /var/lib/apt/lists/*

# IsaacSim 빌드 단계
FROM isaac-deps AS isaac-built

RUN . /opt/ros/humble/setup.bash && \
    colcon build --symlink-install

# Ouster 워크스페이스 준비 단계
FROM isaac-built AS ouster-workspace

ENV OUSTER_WS_ROOT=/root/ouster_ws
ENV OUSTER_WS_SRC=${OUSTER_WS_ROOT}/src

# Ouster 소스 클론
RUN mkdir -p ${OUSTER_WS_SRC}
WORKDIR ${OUSTER_WS_SRC}
RUN git clone --branch ros2 --recurse-submodules https://github.com/ouster-lidar/ouster-ros.git

# Ouster 의존성 설치 및 빌드 단계
FROM ouster-workspace AS ouster-built

WORKDIR ${OUSTER_WS_ROOT}

# Ouster 의존성 설치
RUN . /opt/ros/humble/setup.bash && \
    apt-get update && \
    rosdep install --from-paths src --ignore-src -r -y --rosdistro humble && \
    rm -rf /var/lib/apt/lists/*

# Ouster 빌드
RUN . /opt/ros/humble/setup.bash && \
    colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release

# ============================================================================
# Runtime Stage - 기본 설정
# ============================================================================
FROM ros:humble-ros-base-jammy AS runtime-base

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
        libgl1-mesa-glx \
        libx11-6 \
        libxext6 \
        libxrandr2 \
        libxcursor1 \
    && rm -rf /var/lib/apt/lists/*

# ROS 패키지 설치 (별도 레이어)
FROM runtime-graphics AS runtime-ros

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ros-humble-rviz2 \
        ros-humble-rmw-fastrtps-cpp \
        ros-humble-cv-bridge \
        libpcap-dev \
        # === Nav2 + SLAM  ===
        ros-humble-nav2-bringup \
        ros-humble-slam-toolbox \
        ros-humble-robot-localization \
        ros-humble-dwb-plugins \
    && rm -rf /var/lib/apt/lists/*

# Intel RealSense 설정 및 설치
FROM runtime-ros AS runtime-realsense

RUN echo "Setting up Intel RealSense APT repository..." && \
    mkdir -p /etc/apt/keyrings && \
    curl -sSf https://librealsense.intel.com/Debian/librealsense.pgp | tee /etc/apt/keyrings/librealsense.pgp > /dev/null && \
    echo "deb [signed-by=/etc/apt/keyrings/librealsense.pgp] https://librealsense.intel.com/Debian/apt-repo $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/librealsense.list

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        librealsense2-utils \
        librealsense2-dev \
        librealsense2-gl-dev \
    && rm -rf /var/lib/apt/lists/*

# Clearpath 저장소 설정 (별도 레이어)
FROM runtime-realsense AS runtime-clearpath-setup

RUN echo "Setting up Clearpath Robotics APT repository..." && \
    mkdir -p /usr/share/keyrings && \
    curl -fsSL https://packages.clearpathrobotics.com/public.key | gpg --dearmor -o /usr/share/keyrings/clearpath-archive-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/clearpath-archive-keyring.gpg] \
    https://packages.clearpathrobotics.com/stable/ubuntu jammy main" > /etc/apt/sources.list.d/clearpath-robotics.list

# Clearpath 패키지 설치 (별도 레이어)
FROM runtime-clearpath-setup AS runtime-clearpath

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ros-humble-clearpath-robot \
        ros-humble-clearpath-simulator \
        ros-humble-clearpath-config \
        ros-humble-clearpath-generator-common \
        ros-humble-robot-upstart \
        ros-humble-xacro \
    && rm -rf /var/lib/apt/lists/*

# RealSense ROS 패키지 설치 (별도 레이어)
FROM runtime-clearpath AS runtime-realsense-ros

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ros-humble-realsense2-camera \
        ros-humble-realsense2-description \
    && rm -rf /var/lib/apt/lists/*

# 설정 파일 복사 단계
FROM runtime-realsense-ros AS runtime-configs

# 디렉토리 생성 및 설정 파일 복사
RUN mkdir -p /configs /etc/clearpath

COPY /src/husky_isaac_bringup/config/robot.yaml /etc/clearpath/robot.yaml
COPY /src/husky_isaac_bringup/config/driver_params.yaml /configs/ouster_driver_params.yaml
COPY /src/husky_isaac_bringup/config/ouster_param.yaml /configs/ouster_param.yaml

# Clearpath 설정 생성 단계
FROM runtime-configs AS runtime-clearpath-gen

RUN echo "Generating Clearpath platform scripts and configurations..." && \
    . /opt/ros/humble/setup.bash && \
    echo "Executing generate_bash..." && \
    ros2 run clearpath_generator_common generate_bash --setup_path /etc/clearpath && \
    echo "Executing generate_description..." && \
    ros2 run clearpath_generator_common generate_description --setup_path /etc/clearpath && \
    echo "Executing generate_param..." && \
    ros2 run clearpath_generator_robot generate_param --setup_path /etc/clearpath && \
    echo "Executing generate_launch..." && \
    ros2 run clearpath_generator_robot generate_launch --setup_path /etc/clearpath && \
    echo "Clearpath generation completed."

# Python 라이브러리 설치 (별도 레이어)
FROM runtime-clearpath-gen AS runtime-python-libs

RUN pip3 install --no-cache-dir kafka-python requests

# 빌드된 워크스페이스 복사 단계
FROM runtime-python-libs AS runtime-workspaces

# IsaacSim 워크스페이스 복사
ENV HOST_LIKE_WORKSPACE_ROOT=/root/isaac_sim_ros_ws
COPY --from=isaac-built ${HOST_LIKE_WORKSPACE_ROOT} ${HOST_LIKE_WORKSPACE_ROOT}

# Ouster 워크스페이스 복사
ENV OUSTER_WS_ROOT=/root/ouster_ws
COPY --from=ouster-built ${OUSTER_WS_ROOT} ${OUSTER_WS_ROOT}

# 최종 단계 - 애플리케이션 파일 복사
FROM runtime-workspaces AS final

RUN mkdir -p /root/app_ws

COPY src/ /root/app_ws/src/

#독립 스크립트 복사
COPY standalone_scripts/ /root/standalone_scripts/


WORKDIR /root

# bash 접속 시 ROS Humble 환경 자동 source
RUN echo 'source /opt/ros/humble/setup.bash' >> /root/.bashrc

COPY entrypoint.sh /ros_entrypoint.sh
RUN chmod +x /ros_entrypoint.sh

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]