"""


--- 작성일 :2024.05.01 송인용 ---
23년도에는 처음으로 Omniverse 사용하면서 Backend 작업할때 DB 설정 안하고 하드 코딩으로 아이디 매칭해서 사용했는데,
이번에 작업하면서 같이 테이블에 미리 넣어놓고 사용하는 방식으로 변경했습니다.

tag_ids 는 kube_id(쿠버네티스에서 관리되고 있는 NUC PC id)와 실제 물리적으로 NUC PC 마다 부착된 tag_id(Sewio UWB RLTS tag_id)를 매칭시켜놓은 딕셔너리입니다.
kube_to_nuc 는 kube_id를 NUC PC 이름을 매칭시켜놓은 딕셔너리입니다.

"""



import json
import psycopg2


tag_ids = {
"cafd5a3e-19ba-3a14-df21-1c697ad50493":"24",
"18e1df49-96e8-8e0b-edb6-1c697ad506b6":"40",
"13011dc2-7ced-e6c1-150b-1c697ad507a6":"39",
"efdb1771-5f9f-a027-d863-1c697ad5013e":"37",
"653fbdde-3267-14f1-360e-1c697ad502d0":"36",
"0adbb676-cb42-0882-ce12-1c697ad506cb":"31",
"37dd943b-4abb-a777-224b-1c697ad50558":"49",
"784a8a47-0153-1f8a-ffd3-1c697ad50485":"25",
"90a0fd91-ade8-69bc-f4a1-1c697ad5079b":"44",
"b80cc5d8-e1be-f6b8-a03e-1c697ad5015f":"23",
"fc1258ba-b25c-2724-d6d7-1c697ad99de0":"20",
"fe47eb1b-cf4c-f3fb-5057-1c697ad99f56":"22",
"02ca34fa-a216-9a2b-2a0a-1c697ad8c177":"46",
"9bc3697d-072e-dc48-29fb-1c697ad99e51":"19",
"9bcc45d1-c926-ab80-b3c0-1c697ad99d94":"45",
"92404821-7051-5c93-90bd-1c697ad8c045":"29",
"9f351faf-d85c-e39e-1e64-1c697ad8c10d":"18",
"5c85978f-e920-9ebf-9334-1c697ad8c107":"33",
"da454806-2e36-f088-f10e-1c697ad8c03f":"43",
"3adacb41-faad-9484-7477-1c697ad8c17d":"26",
"99effe4d-6ea9-56a4-c5c8-1c697ad99dc1":"48",
"a9fa482b-1e0a-e75e-2236-1c697ad99f5f":"41",
"11b95e87-0f9f-391b-2357-1c697ad8bfea":"21",
"ffb521e3-8dea-0d79-65fb-1c697ad8c124":"35",
"e4020aba-4b62-55fa-1362-1c697ad99df2":"47",
"cb47d8b7-008b-d945-c9e1-1c697ad8c0b9":"38",
"1e35b5a9-ca19-33f3-94b3-1c697ad99f0c":"9",
"5f0e2f32-c2f8-e3a8-a6f9-1c697ad8c015":"34",
"895927f7-5f36-b840-731e-1c697ad99eb0":"32",
"c2136df7-8483-22eb-3210-1c697ad99e00":"42"

}

kube_to_nuc = {
"cafd5a3e-19ba-3a14-df21-1c697ad50493":"NUC11_01",
"18e1df49-96e8-8e0b-edb6-1c697ad506b6":"NUC11_02",
"13011dc2-7ced-e6c1-150b-1c697ad507a6":"NUC11_03",
"efdb1771-5f9f-a027-d863-1c697ad5013e":"NUC11_04",
"653fbdde-3267-14f1-360e-1c697ad502d0":"NUC11_05",
"0adbb676-cb42-0882-ce12-1c697ad506cb":"NUC11_06",
"37dd943b-4abb-a777-224b-1c697ad50558":"NUC11_07",
"784a8a47-0153-1f8a-ffd3-1c697ad50485":"NUC11_08",
"90a0fd91-ade8-69bc-f4a1-1c697ad5079b":"NUC11_09",
"b80cc5d8-e1be-f6b8-a03e-1c697ad5015f":"NUC11_10",
"fc1258ba-b25c-2724-d6d7-1c697ad99de0":"NUC12_01",
"fe47eb1b-cf4c-f3fb-5057-1c697ad99f56":"NUC12_02",
"02ca34fa-a216-9a2b-2a0a-1c697ad8c177":"NUC12_03",
"9bc3697d-072e-dc48-29fb-1c697ad99e51":"NUC12_04",
"9bcc45d1-c926-ab80-b3c0-1c697ad99d94":"NUC12_05",
"92404821-7051-5c93-90bd-1c697ad8c045":"NUC12_06",
"9f351faf-d85c-e39e-1e64-1c697ad8c10d":"NUC12_07",
"5c85978f-e920-9ebf-9334-1c697ad8c107":"NUC12_08",
"da454806-2e36-f088-f10e-1c697ad8c03f":"NUC12_09",
"3adacb41-faad-9484-7477-1c697ad8c17d":"NUC12_10",
"99effe4d-6ea9-56a4-c5c8-1c697ad99dc1":"NUC12_11",
"a9fa482b-1e0a-e75e-2236-1c697ad99f5f":"NUC12_12",
"11b95e87-0f9f-391b-2357-1c697ad8bfea":"NUC12_13",
"ffb521e3-8dea-0d79-65fb-1c697ad8c124":"NUC12_14",
"e4020aba-4b62-55fa-1362-1c697ad99df2":"NUC12_15",
"cb47d8b7-008b-d945-c9e1-1c697ad8c0b9":"NUC12_16",
"1e35b5a9-ca19-33f3-94b3-1c697ad99f0c":"NUC12_17",
"5f0e2f32-c2f8-e3a8-a6f9-1c697ad8c015":"NUC12_18",
"895927f7-5f36-b840-731e-1c697ad99eb0":"NUC12_19",
"c2136df7-8483-22eb-3210-1c697ad99e00":"NUC12_20"
}


# config.json 파일에서 설정 로드
with open('/home/netai/dt_server/UWB_EKF/config.json', 'r') as file:
    config = json.load(file)

# 데이터베이스 연결 설정
conn_string = f"host={config['db_host']} port={config['db_port']} dbname={config['db_name']} user={config['db_user']} password={config['db_password']}"

# 데이터베이스에 연결
conn = psycopg2.connect(conn_string)
conn.autocommit = True  # 자동 커밋 활성화

# 커서 생성
cursor = conn.cursor()


# SQL 쿼리 실행
for kube_id, nuc_id in kube_to_nuc.items():
    tag_id = tag_ids[kube_id]
    query = f"INSERT INTO uwb_tag (tag_id, kube_id, nuc_id) VALUES ({tag_id}, '{kube_id}', '{nuc_id}');"
    cursor.execute(query)

# 데이터베이스 연결 종료
cursor.close()
conn.close()

print("Data insertion complete.")