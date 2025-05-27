# 베이스 이미지: ROS 2 Humble (Ubuntu Jammy) # 빌더 스테이지
FROM ros:humble-ros-base-jammy AS builder

# APT 패키지 설치 시 상호작용 프롬프트 비활성화
ARG DEBIAN_FRONTEND=noninteractive

# RUN 명령어에 사용할 기본 쉘을 bash로 설정
SHELL ["/bin/bash", "-c"]

# 시스템 업데이트 및 필수 도구 설치
RUN apt-get update && \
    apt-get install -y \
        git \
        python3-pip \
        python3-venv \
        python3-colcon-common-extensions \
        ros-humble-rmw-fastrtps-cpp \
    && rm -rf /var/lib/apt/lists/*

# --- IsaacSim-ros_workspaces 관련 부분 (새로 빌드한다면 경로 수정 잘할것  Dockerfile 기준 유지) ---
ENV HOST_LIKE_WORKSPACE_ROOT=/root/isaac_sim_ros_ws
ENV ROS2_WS_SRC=${HOST_LIKE_WORKSPACE_ROOT}/src
RUN mkdir -p ${ROS2_WS_SRC}
WORKDIR ${ROS2_WS_SRC}
RUN git clone https://github.com/NVIDIA-Omniverse/IsaacSim-ros_workspaces.git
WORKDIR ${ROS2_WS_SRC}/IsaacSim-ros_workspaces/humble_ws
RUN . /opt/ros/humble/setup.bash && \
    apt-get update && \
    rosdep init || true && \
    rosdep update && \
    rosdep install -i --from-paths src --rosdistro humble -y --skip-keys "isaac_sim_μέρος_python_venv rviz_ogre_vendor"
RUN . /opt/ros/humble/setup.bash && \
    colcon build --symlink-install
# --- 여기까지 IsaacSim-ros_workspaces 관련 부분 ---

# --- Ouster LiDAR Driver Workspace (ouster_ws) 빌드 ---
ENV OUSTER_WS_ROOT=/root/ouster_ws
ENV OUSTER_WS_SRC=${OUSTER_WS_ROOT}/src
RUN mkdir -p ${OUSTER_WS_SRC}
WORKDIR ${OUSTER_WS_SRC}
RUN git clone --branch ros2 --recurse-submodules https://github.com/ouster-lidar/ouster-ros.git
WORKDIR ${OUSTER_WS_ROOT}
RUN . /opt/ros/humble/setup.bash && \
    rosdep install --from-paths src --ignore-src -r -y --rosdistro humble
RUN . /opt/ros/humble/setup.bash && \
    colcon build --cmake-args -DCMAKE_BUILD_TYPE=Release
# --- 여기까지 Ouster LiDAR Driver Workspace (ouster_ws) 빌드 ---


# --- Runtime Stage ---
FROM ros:humble-ros-base-jammy

ARG DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]
# RMW 구현을 FastDDS로 명시적으로 설정(Omniverse Isaac Sim 공식 권장 사항)
ENV RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# --- 여기부터 설정 파일 복사 ---

# robot.yaml 파일 복사
RUN mkdir -p /configs /etc/clearpath

COPY robot.yaml /etc/clearpath/robot.yaml

# Ouster LiDAR용 driver_params.yaml 파일 복사
COPY driver_params.yaml /configs/ouster_driver_params.yaml
# --- 여기까지 설정 파일 복사 ---

# 런타임에 필요한 패키지 설치 및 Clearpath 저장소 설정
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        # Clearpath 저장소 설정에 필요한 도구
        curl \
        gnupg \
        lsb-release \
        apt-transport-https \
        software-properties-common \        
        # 기존 의존성
        python3-pip \
        python3-venv \
        python3-yaml \
        libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
        ros-humble-rviz2 \
        ros-humble-rmw-fastrtps-cpp \
        libpcap-dev \
        ros-humble-cv-bridge \
        python3-opencv \
    && \

    # --- Intel RealSense 저장소 추가 및 SDK 설치 ---
        echo "Setting up Intel RealSense APT repository..." && \
        mkdir -p /etc/apt/keyrings && \
        curl -sSf https://librealsense.intel.com/Debian/librealsense.pgp | tee /etc/apt/keyrings/librealsense.pgp > /dev/null && \
        echo "deb [signed-by=/etc/apt/keyrings/librealsense.pgp] https://librealsense.intel.com/Debian/apt-repo $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/librealsense.list && \
        apt-get update && \
        echo "Installing Intel RealSense SDK packages..." && \
        apt-get install -y --no-install-recommends \
            librealsense2-utils \
            librealsense2-dev \
            librealsense2-gl-dev \
        && \

    # Clearpath Robotics APT 저장소 설정 시작
    echo "Setting up Clearpath Robotics APT repository..." && \
    mkdir -p /usr/share/keyrings && \
    curl -fsSL https://packages.clearpathrobotics.com/public.key | gpg --dearmor -o /usr/share/keyrings/clearpath-archive-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/clearpath-archive-keyring.gpg] \
    https://packages.clearpathrobotics.com/stable/ubuntu jammy main" > /etc/apt/sources.list.d/clearpath-robotics.list && \
    apt-get update && \
    # --- Clearpath Husky A200 패키지 설치 ---    
    echo "Installing Clearpath Husky A200 packages..." && \
    apt-get install -y --no-install-recommends \
        ros-humble-clearpath-robot \
        ros-humble-clearpath-simulator \
        ros-humble-clearpath-config \
        ros-humble-clearpath-generator-common \
        ros-humble-robot-upstart \
        ros-humble-xacro \
        ros-humble-realsense2-camera \
        ros-humble-realsense2-description \        
    && \
    echo "Attempting to generate Clearpath platform scripts and configurations using ros2 run..." && \
    . /opt/ros/humble/setup.bash && \
    # generate_bash: /etc/clearpath/setup.bash 생성
    echo "Executing ros2 run clearpath_generator_common generate_bash..." && \
    ros2 run clearpath_generator_common generate_bash --setup_path /etc/clearpath && \
    # generate_description: /etc/clearpath/robot.urdf.xacro 등 생성
    echo "Executing ros2 run clearpath_generator_common generate_description..." && \
    ros2 run clearpath_generator_common generate_description --setup_path /etc/clearpath && \
    # generate_param: YAML 파라미터 파일들 생성 (예: /etc/clearpath/platform/config/control.yaml)
    echo "Executing ros2 run clearpath_generator_robot generate_param --setup_path /etc/clearpath..." && \
    ros2 run clearpath_generator_robot generate_param --setup_path /etc/clearpath && \
    # generate_launch: /etc/clearpath/launch/ 디렉토리 및 launch 파일들 생성
    echo "Executing ros2 run clearpath_generator_robot generate_launch --setup_path /etc/clearpath..." && \
    ros2 run clearpath_generator_robot generate_launch --setup_path /etc/clearpath && \
    echo "Clearpath generation scripts executed via ros2 run. Check /etc/clearpath/ for generated files." && \
    # APT 캐시 정리
    rm -rf /var/lib/apt/lists/*


# <<<--- 여기부터 kafka-python 등 필요한 라이브러리들 있으면 설치
RUN pip3 install kafka-python requests

# --- IsaacSim-ros_workspaces 관련 부분 ---
ENV HOST_LIKE_WORKSPACE_ROOT=/root/isaac_sim_ros_ws
COPY --from=builder ${HOST_LIKE_WORKSPACE_ROOT} ${HOST_LIKE_WORKSPACE_ROOT}
# --- 여기까지 IsaacSim-ros_workspaces 관련 부분 ---

# --- Ouster LiDAR Driver Workspace (ouster_ws) 복사 ---
ENV OUSTER_WS_ROOT=/root/ouster_ws
COPY --from=builder ${OUSTER_WS_ROOT} ${OUSTER_WS_ROOT}

# --- 그 외 필요한 테스트나 ROS2 용 코드들 있으면 여기서 복사사 키보드 왜 이래ㅔㅅ .ㅇ ---
COPY simple_subscriber.py /root/simple_subscriber.py
COPY pointcloud_to_kafka.py /root/pointcloud_to_kafka.py
COPY fastdds_force_udp.xml /etc/fastdds/fastdds_force_udp.xml
COPY ros2_camera_to_kafka_agent.py /root/ros2_camera_to_kafka_agent.py
WORKDIR /root

# ============================================================================ #
# =================== bash 접속 시 ROS Humble 환경 자동 source =================== #
# ============================================================================ #
RUN echo 'source /opt/ros/humble/setup.bash' >> /root/.bashrc

COPY entrypoint.sh /ros_entrypoint.sh
RUN chmod +x /ros_entrypoint.sh

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]