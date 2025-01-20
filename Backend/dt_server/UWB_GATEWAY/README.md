# Omniverse UWB GATEWAY

Omniverse 기반 Digital Twin 프로젝트중 처음으로 MVC 패턴 + IOC/DI 위주로 좀 더 체계적으로 개발한 웹개발 서버

기능은 크게 두가지임

1.Sewio RLTS 서버 웹소켓 연결해서 실제 데이터를 Omniverse 로 전달 
2. REST API 로 사용자가 실시간으로 Filter 를 어떤걸 사용할지등 데이터 처리 변경 요청을 받아서 수행하는 역할


모든 UWB 데이터 처리는 일단은 해당 서버를 거치고 Omniverse 로 전송되도록함 
Sewio RLTS 서버에서 웹소켓으로 데이터가 넘어오면 현재 설정된 조건에 맞춰 데이터를 KAFKA 로 전송하도록 구현함

물리적 UWB 데이터 처리는 Omniverse 는 순수 Consumner 로써 UWB Extension은 Kafka 로 데이터 수신 받으면, 해당 Tag 가 움직인 거리 만큼 움직임 끝

User : Rest API로 특정 Tag 나 전체 Tag 별로 원하는 필터 적용 할지 유무 여부 결정 (Strategy 패턴 유사하다면 유사)




---
그 외 태그별로 어느 Object 가 매핑되는지 (로봇인지, MobileX Station 인지 아니면 사람 처럼 별개의 Object) 인지

사용자가 지정한 MobileX Station 정렬 정보로 이동 같은 기능도 여기에 구현함

사실 MSA에서 기능별로 분리한다는 관점에서 보면 이런 기능은 별개의 서버로 분리하는게 좋겠지만 시간 문제상 해당 기능도 통합해서 묶었음



