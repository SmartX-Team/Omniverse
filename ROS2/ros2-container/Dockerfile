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


# --- Runtime Stage ---
FROM ros:humble-ros-base-jammy

ARG DEBIAN_FRONTEND=noninteractive

# RMW 구현을 FastDDS로 명시적으로 설정(Omniverse Isaac Sim 공식 권장 사항)
ENV RMW_IMPLEMENTATION=rmw_fastrtps_cpp

# 런타임에 필요한 패키지 설치
RUN apt-get update && \
    apt-get install -y \
        python3-pip \
        python3-venv \
        ros-humble-rmw-fastrtps-cpp \
    && rm -rf /var/lib/apt/lists/*

# <<<--- 여기에 kafka-python 등 필요한 라이브러리들 있으면 설치
RUN pip3 install kafka-python

# --- IsaacSim-ros_workspaces 관련 부분 ---
ENV HOST_LIKE_WORKSPACE_ROOT=/root/isaac_sim_ros_ws
COPY --from=builder ${HOST_LIKE_WORKSPACE_ROOT} ${HOST_LIKE_WORKSPACE_ROOT}
# --- 여기까지 IsaacSim-ros_workspaces 관련 부분 ---

COPY simple_subscriber.py /root/simple_subscriber.py
COPY pointcloud_to_kafka.py /root/pointcloud_to_kafka.py
COPY fastdds_force_udp.xml /etc/fastdds/fastdds_force_udp.xml

WORKDIR /root

COPY entrypoint.sh /ros_entrypoint.sh
RUN chmod +x /ros_entrypoint.sh

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]