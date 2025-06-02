# Omniverse Backend Repository

해당 Repo 는 UWB 데이터 -> PostgreSQL 적재, EKF 기반 UWb + IMU 센서 퓨징, 시연을 위해 테스트해본 UWB 데이터를 외부 클라우드로 전송하는 기본 Docker compose 기반 인프라 세팅 코드 등이 담겨 있습니다.

현재는 UWB 적재를 위한 Omniverse/Backend/dt_server/UWB_Raw 를 제외하고는 거의다 Deprecated 되어 있으나
후에 ROS2 랑 연계를 위햐 EKF 코드 리팩토링 및 재 사용 할 수도 있습니다.

This repository contains UWB data ingestion to PostgreSQL, EKF-based UWB + IMU sensor fusion, basic Docker Compose-based infrastructure setup code for transmitting UWB data to external cloud for demonstration testing, and more.
Currently, most components are deprecated except for Omniverse/Backend/dt_server/UWB_Raw which is used for UWB data ingestion. However, the EKF code may be refactored and reused for future integration with ROS2.