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
├── entrypoint.sh
├── fastdds_force_udp.xml
└── simple_subscriber.py  # 테스트용 Python 구독 스크립트 (선택 사항)

## 3. 설정 및 실행 절차

### 단계 1: 호스트 머신에서 Isaac Sim 실행 환경 준비

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


컨테이너 내부 아이작심과 동작 테스트 명령어어:

ros2 topic list
ros2 topic echo /pointcloud
