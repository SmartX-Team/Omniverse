# 베이스 이미지: ROS 2 Humble
FROM ros:humble-ros-base-jammy

ARG DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

# 1. 시스템 의존성 및 ROS 2 빌드 도구 설치
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-pip \
        python3-venv \
        python3-colcon-common-extensions \
        ros-humble-rmw-fastrtps-cpp \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --upgrade "pip<24.0" "setuptools==65.5.1"
RUN python3 -m pip install --no-cache-dir ament_index_python==1.6.0

# 2. Python 강화학습(RL) 라이브러리 설치
RUN pip3 install \
    stable-baselines3[extra] \
    gymnasium \
    torch \
    --extra-index-url https://download.pytorch.org/whl/cu118

# 3. ROS 2 워크스페이스 준비
ENV NAV_WS=/root/nav_ws
RUN mkdir -p ${NAV_WS}/src
WORKDIR ${NAV_WS}

# 4. 소스 코드 복사
COPY src/ ${NAV_WS}/src/

# 5. ROS 2 의존성 설치
RUN . /opt/ros/humble/setup.bash && \
    apt-get update && \
    rosdep init || true && \
    rosdep update && \
    rosdep install --from-paths src --ignore-src -r -y --rosdistro humble

# 6. ROS 2 워크스페이스 빌드 (이 단계가 성공하면 install 폴더가 생성됨)
RUN . /opt/ros/humble/setup.bash && \
    rm -rf /root/nav_ws/install /root/nav_ws/build /root/nav_ws/log && \
    colcon build --symlink-install

# 7. 실행 권한 부여 및 Entrypoint 설정
RUN find ${NAV_WS}/src/ugv_nav -type f -name "*.py" -exec chmod +x {} +

# entrypoint.sh 복사 및 실행 권한 부여
COPY .docker/entrypoint.sh /ros_entrypoint.sh
RUN chmod +x /ros_entrypoint.sh

ENTRYPOINT ["/ros_entrypoint.sh"]
CMD ["bash"]