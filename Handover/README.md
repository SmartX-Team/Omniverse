## 작성자 및 문서 목적

- **작성자:** 송인용 (석사과정 재학 중 구축)
- **레포 성격:** 본 저장소는 송인용이 석사과정 동안 수행한 **Omniverse 기반 디지털 트윈/시뮬레이션 작업 코드(Extensions, ROS2 연동, 백엔드 구성)** 가 모여 있는 통합 Repository입니다.
- **현재 목적:** 본 문서는 프로젝트 **인수인계(Handover)** 를 위해 남겨진 운영/실행 중심 문서입니다.

> `Handover/` 폴더는 인수인계 범위를 **로보틱스(UGV) 시뮬레이션 및 sim-to-real 검증**으로 한정하여, Isaac Sim 연동 중심의 실행 방법/점검/트러블슈팅을 정리합니다.

---

# Handover Hub (로보틱스 시뮬레이션 인수인계 허브)

이 폴더는 Omniverse Extensions Repository의 **로보틱스 인수인계 문서 허브**입니다.  
새로운 담당자가 아래를 빠르게 수행하도록 구성했습니다:

- 로보틱스 중심 **시스템 맥락** 이해
- 개발/런타임 **환경 구축**
- **최소 동작 워크플로우** 실행
- 자주 발생하는 문제 **트러블슈팅**
- 로보틱스 시뮬레이션 및 연동을 **안전하게 운영/유지**

> 범위 안내  
> - 루트의 `README.md`는 저장소의 전체 목적/구조를 설명합니다.  
> - `Handover/` 는 **로보틱스 시뮬레이션(Isaac Sim) + ROS2 연동 + sim-to-real 테스트 예시**에 필요한 실무 지식만 다룹니다.

---

## Overview: 이 인수인계를 따라하면 가능한 연구 범위

이 문서를 그대로 따라가면, 아래 3가지 범위의 작업을 재현/검증할 수 있습니다.


10)  **현실 Husky UGV 다루는 법**  
- 실제 Husky UGV를 기본 안전 수칙 하에 구동하고, ROS2 기반으로 최소 제어/상태 확인을 수행

20)  **가상 Husky UGV 시뮬레이션 동작하는 법**  
- Isaac Sim(Omniverse)에서 Husky UGV 시뮬레이션을 구동하고, 센서/상태/제어 루프가 정상 동작하는지 확인

30)  **Sim-to-Real 테스트 예시**  
- 동일(또는 유사)한 제어/토픽 구조를 기준으로 시뮬레이터 ↔ 실기체 간 전환 테스트를 수행하는 예시 워크플로우 제공


---

## Document Index (최소 구성)

- **[00 - Overview](./00-overview.md)**  
  로보틱스 인수인계 범위, 실행 환경, 실행 보장 목표, 주요 리스크, “무엇부터 할지” 정리

- **[10 - Real Husky UGV Guide](./10-real-husky-ugv-guide.md)**  
  현실 Husky UGV 기본 운용(안전 수칙 포함), ROS2 기반 최소 제어/상태 확인 절차

- **[20 - Sim Husky UGV Bringup](./20-sim-husky-ugv-bringup.md)**  
  Isaac Sim(Omniverse)에서 Husky UGV 시뮬레이션 구동, 센서/상태/제어 루프 검증

- **[30 - Sim-to-Real Test Examples](./30-sim-to-real-examples.md)**  
  동일(또는 유사)한 제어/토픽 구조를 기준으로 시뮬레이터 ↔ 실기체 전환 테스트 예시 워크플로우

- **[90 - Troubleshooting](./90-troubleshooting.md)**
  실행 실패/환경 불일치/ROS2 연동 문제 등 **증상 → 진단 → 해결**을 빠르게 찾기 위한 문제 해결 가이드

---

## Folder Convention (Robotics Scope)

- `00-` : Overview / 범위 및 목표
- `90-` : Troubleshooting (로보틱스 연동 문제 해결)
- `assets/` : 인수인계용 이미지/다이어그램/스크린샷
