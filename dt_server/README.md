# Omniverse Backend Project

Omniverse 기반 Digital Twin 프로젝트중 Backend Code 정리 Branch 입니다.

코드 정리 및 상세한 설명은 조만간 진행할 예정입니다.

* DISPLAY_Streaming : Visualization Center 의 Display Wall 모니터 화면을 스트리밍하면서 Dream-AI 가상 모델 안의 Display Wall 과 동기화 할 수 있도록 지원해주는 서버
* Kubernetes: MobileX Station 과 같이 현재 쿠버네티스 기반으로 관리되고 있는 데이터를 수집하고 디지털 트윈으로 전달하는 서버 코드 모음
  - Power_Info: 현재 각 Station들의 전원 상태 및 로그인 상태 정보를 수집해서 디지털 트윈으로 전달하는 서버
  - System_Stat: 현재 각 Station들의 CPU, GPU 사용량등 자원 사용률 데이터 수집해서 디지털 트윈으로 전달하는 서버(현재 개발중)
* UWB_Raw : UWB Raw 데이터를 정제및 카프카로 DT에 전송 및 DB에 저장
* UWB_EKF : UWB 오차를 보정하기 위해 로봇 IMU 데이터와 실시간으로 결합하면서 오차 측정을 위해 만든 서버 기능,  논문 쓸려고 만듬

***

This is a branch for organizing the backend code of a Digital Twin project based on Omniverse.
Detailed code organization and explanations will be conducted soon.

* DISPLAY_Streaming: A server that supports streaming the screen of the Visualization Center's Display Wall monitor and synchronizing it with the Display Wall inside the Dream-AI virtual model.

* Kubernetes: A collection of server codes that gather data currently managed based on Kubernetes, such as MobileX Station, and deliver it to the Digital Twin.
  - Power_Info: A server that collects power status and login status information of each station and delivers it to the Digital Twin.
  - System_Stat: A server (currently under development) that collects resource usage data such as CPU and GPU usage of each station and delivers it to the Digital Twin.
* UWB_Raw : Process UWB raw data, send it to DT via Kafka, and store it in the database.
* UWB_EKF: A server function created to correct UWB errors by combining robot IMU data in real-time for error measurement, intended for writing a paper.
