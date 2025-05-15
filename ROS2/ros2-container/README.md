# ReadMe.md: Isaac Sim (호스트) - 컨테이너 기반반 ROS 2 Humble Docker 연동 가이드

## 1. 개요

이 문서는 NVIDIA Isaac Sim (호스트 머신에서 실행)과 ROS 2 Humble Docker 컨테이너 간의 안정적인 통신 환경 설정을 안내합니다. 제공된 `Dockerfile`, `entrypoint.sh`, `fastdds_force_udp.xml` 등의 코드를 사용하여, Isaac Sim이 발행하는 Docker 컨테이너 기반에서 ROS 2 환경을 구성하고 운 것을 목표로 합니다.

미리 빌드한 도커 컨테이너 경로: docker pull ttyy441/ros2-container

## 2. 사전 요구 사항

### 2.1. 호스트 머신 환경

- **운영 체제:** Ubuntu 22.04 LTS 권장
- **NVIDIA Isaac Sim:** 4.5 ;
- **Docker 엔진:** 최신 버전 설치 
- **NVIDIA 드라이버:** 테스트는 535 버전에서 진행하였음음
- **NVIDIA Container Toolkit:** 설치 완료

<project_root>/
├── Dockerfile
├── entrypoint.sh            # 컨테이너 시작 시 실행되는 스크립트
├── robot.yaml               # Husky A200 로봇 구성 파일 (Clearpath용)
├── fastdds_force_udp.xml    # Isaac Sim 연동 시 FastDDS UDP 강제 설정
├── ouster_driver_params.yaml # Ouster LiDAR 파라미터 파일 (Ouster 사용 시)
└── simple_subscriber.py     # (선택 사항) 테스트용 아이작심에서 생성한 Lidar 데이터 전송 스크립트 / 그 외 필요한 스크립트들 있다면 추가

## 3. 설정 및 실행 절차


### 3.1. Dockerfile
제공된 Dockerfile은 두 단계(builder, runtime)로 구성되어 있으며, Husky A200 운영 및 Isaac Sim, Ouster LiDAR 연동에 필요한 모든 환경을 설정합니다.

현재 현재 사용중인 Husky UGV clearpath 의 로봇 관련 패키지들이 지속적으로 구조가 변경되고 있어 현재 제가 작성했던 구조랑 달라질 수 있음은 숙지 바람

주요 설치 패키지 (Runtime Stage):
ros-humble-clearpath-robot: Husky A200 운영을 위한 핵심 메타패키지. 이 패키지가 ros-humble-clearpath-hardware-interfaces, ros-humble-clearpath-control, ros-humble-clearpath-description, ros-humble-clearpath-msgs, ros-humble-clearpath-sensors, ros-humble-clearpath-generator-robot 등 대부분의 필수 의존성을 자동으로 설치합니다. 

ros-humble-clearpath-simulator: 시뮬레이션 관련 도구 (선택적 포함 가능)
ros-humble-clearpath-config: robot.yaml 처리 등 설정 관련 도구
ros-humble-clearpath-generator-common: 공통 설정 생성 도구
ros-humble-robot-upstart: 시스템 서비스 관련 유틸리티 (컨테이너에서는 직접적인 서비스 등록보다 스크립트 제공에 의미)
ros-humble-xacro: URDF 처리에 필요

### 3.2 entrypoint.sh
컨테이너 시작 시 실행되는 핵심 스크립트입니다.

모드 선택: docker run 시 첫 번째 인자로 isaac_sim (또는 isaac_sim_default) 또는 real_robot 모드를 선택할 수 있습니다. 기본값은 isaac_sim_default입니다.
환경 소싱: 선택된 모드에 따라 필요한 setup.bash 파일들을 순서대로 source합니다.
공통: /opt/ros/humble/setup.bash

isaac_sim 모드: Isaac Sim 워크스페이스의 setup.bash
real_robot 모드: /etc/clearpath/setup.bash (Clearpath 생성 환경), Ouster 워크스페이스 setup.bash (존재 시)
real_robot 모드 자동 실행 및 설정:
MCU 시리얼 포트 심볼릭 링크 생성: Husky MCU와의 통신을 위해, 호스트의 /dev/ttyUSB0 (또는 실제 연결된 장치명)을 컨테이너 내에서 /dev/clearpath/prolific으로 연결하는 심볼릭 링크를 자동으로 생성합니다. 이는 A200Hardware 인터페이스가 하드코딩된 경로를 사용할 경우를 대비합니다.

#### !!! 시리얼 포트 번호나 이후 추가적으로 조이스틱등 연결 작업이 들어간다면 해당 부분 신경써서 수정 바람


### 3.3. 설정 파일
robot.yaml: /etc/clearpath/robot.yaml에 위치하며, 로봇의 네임스페이스, 컨트롤러 타입, 장착된 센서 및 액세서리 등 로봇의 모든 하드웨어 구성을 정의합니다. Clearpath generator 스크립트들이 이 파일을 참조하여 다른 설정들을 생성합니다. 매우 중요한 파일입니다. -> Husky URDF 등 추가적인 부속품이나 센서 설치할때 해당 파일 수정후 재빌드 하시면 됩니다.
fastdds_force_udp.xml: 기본 설정이 FastDDS 이긴 하나 Isaac Sim과 ROS 2 간의 DDS 통신 시 안정성을 위해 UDP 사용을 강제하는 FastDDS 프로파일입니다.
ouster_driver_params.yaml: Ouster LiDAR 사용 시 필요한 파라미터들을 정의합니다.



### 4. 호스트 머신에서 Isaac Sim 실행 환경 준비

컨테이너화 시키긴 했지만 여전히 최소한 컨테이너가 실행되는 호스트 머신에서 환경 설정 작업을 해두시길을 권장합니다.
특히 조이스틱이나 MCU 시리얼 포트등 물리적인 UGV 컨트롤할때는 포트 번호등 한번씩 확인하면서 컨테이너에 반영해야합니다.

Isaac Sim을 실행하기 **전에**, Isaac Sim을 시작할 호스트 터미널에서 다음 환경 변수를 설정합니다. 이는 Isaac Sim의 FastDDS가 제공된 XML 프로파일(UDP 강제)을 사용하고, 올바른 RMW 구현을 사용하도록 보장합니다.

```bash
# 호스트 터미널에서 실행

# 1. FASTRTPS_DEFAULT_PROFILES_FILE 환경 변수 설정
#    <project_root>를 실제 코드가 위치한 경로로 변경주의 ; SV4000 #1 PC에는 이미 설정해둠
export FASTRTPS_DEFAULT_PROFILES_FILE="<project_root>/fastdds_force_udp.xml"

# 2. RMW_IMPLEMENTATION 환경 변수 설정
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp


컨테이너 필수 파라미터:

docker run -it --rm \
    --network host \
    --ipc=host \
    --privileged \
    isaac_sim_ros2_link_app


그 외 아이작심 내 가상 UGV 컨트롤 모드

docker run -it --rm \
    --network host \
    --ipc=host \
    --privileged \
ttyy441/ros2-container:0.2 \
isaac_sim

실제 물리적인 Huksy UGV 내 컨트롤 모드로 실행


docker run -it --rm \
    --network host \
    --ipc=host \
    --privileged \
    --device=/dev:/dev/  \
ttyy441/ros2-container:0.2 \
real_robot \
ros2 launch ouster_ros driver.launch.py params_file:=/configs/ouster_driver_params.yaml viz:=false



컨테이너 내부 아이작심과 동작 테스트 명령어어:

ros2 topic list
ros2 topic echo /pointcloud
