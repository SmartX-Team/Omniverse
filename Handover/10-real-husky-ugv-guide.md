# 10 - Real Husky UGV Guide (ROS1 기반 실기체 운용: 주제 소개 + 전제/준비)

- 작성자: 송인용  
- 문서 목적: 처음 연구실에 인계받은 Clearpath 사의 Husky UGV는 ROS1 기반으로 운영되었으나 이후 자체적인 연구실내 작업을 통해 ROS2 Humble로 업그레이드하여 Isaac Sim 시뮬레이션과 연동하였다.  
- 해당 문서에서는 연구실내 보유중인 Clearpath 사의 Husky UGV의  물리적인 운용 방법과 ROS2 기반 세팅 현황을 정리하였다  

---

## Index

### 10. 전체 목차 나열 및 다루는 범위 정리
- 이 주제(10)에서 다루는 범위: 실기체(Husky) 물리 운용 + 연구실 세팅 현황 + 기본 접속/점검 방법  
- 이 주제(10)에서 다루지 않는 범위: 시뮬레이션(Isaac Sim) 내부 설정, ROS2 패키지/런치 상세, sim-to-real 워크플로우(해당 내용은 20/30대 문서에서 다룸)  
- 문서 흐름: 11(공식 소개/부록) → 12(연구실 보유 자산/운용환경) → 13(원격접속) → 14(기본 명령/조작)  

### 11. Clearpath Husky Robot 소개 (공식 페이지 자료 부록)
- 공식 매뉴얼/스펙/안전 규정 정리  

### 12. Net-AI 연구실 보유 Husky Robot 악세서리 및 구동 방법
- 보유 기체/식별 정보(개체 구분), 센서/컨트롤러/네트워크 구성 개요  
- 실기체 운용 시 연구실 로컬 규칙(장비 보관/충전/운용 제약)  

### 13. ROS2 세팅 현황 및 원격접속 방법 (2026-08-15 개정)
- ROS2 Jazzy 마이그레이션 이후의 "현재 세팅 현황" 요약(Humble/Isaac 4.5 시절 내용은 개정판으로 대체)
- 관련 레포/이미지 위치(`ros2-container-real`, `ttyy441/ros2-container-real:1.1-jazzy`) 및 주의사항(TwistStamped, ROS_DOMAIN_ID 0 강제, Ouster 고정 IP)
- 접속 경로: 무선 SSH (유선 포트는 Ouster 전용)  
- 신규 머신 1회 세팅(netplan 고정 IP, sysctl)  
- Humble→Jazzy 전환에서 잡은 트러블슈팅 이력 12건 (같은 증상 만나면 여기부터 확인)  

### 14. ROS2 컨테이너 실행 및 Husky 운용 방법
- 컨테이너 실행 명령(상시 등록/1회성/모드 목록) 및 운용 명령  
- PS5 DualSense 패드 페어링/조작법(L1 데드맨)  
- 정상 가동 검증 명령어(실측 기대값 병기) + TwistStamped 수동 주행 테스트  
- SLAM/Nav2 세션 실행 방법(`start_slam_nav.sh`)