import requests
import pandas as pd
import psycopg2
import json

# config.json 파일에서 설정 로드
with open('/home/netai/Omniverse/dt_server/UWB_EKF/DATA_COLLECTION/config.json', 'r') as file:
    config = json.load(file)

# 데이터베이스 연결 설정
conn_string = f"host={config['db_host']} port={config['db_port']} dbname={config['db_name']} user={config['db_user']} password={config['db_password']}"

# 데이터베이스에 연결
conn = psycopg2.connect(conn_string)

# 커서 생성
cursor = conn.cursor()

# API 호출
api_url = "http://10.76.20.88/sensmapserver/api/anchors"
headers = {
    'X-Apikey': '17254faec6a60f58458308763'
}

response = requests.get(api_url, headers=headers)

# 데이터가 성공적으로 받아졌는지 확인
if response.status_code == 200:
    data = response.json()
    
    # Extracting required information
    anchors_info = []

    for anchor in data["results"]:
        title = anchor["title"].replace('0x', '')
        anchor_info = {
            "Anchor Id": anchor["id"],
            "Alias": anchor["alias"],
            "Address": title,
            "posX": next((stream["current_value"] for stream in anchor["datastreams"] if stream["id"] == "posX"), None),
            "posY": next((stream["current_value"] for stream in anchor["datastreams"] if stream["id"] == "posY"), None),
            "ProductName": next((stream["current_value"] for stream in anchor["datastreams"] if stream["id"] == "productName"), None),
            "Master": next((stream["current_value"] for stream in anchor["datastreams"] if stream["id"] == "master"), None)
        }
        anchors_info.append(anchor_info)

    # Convert to DataFrame
    df = pd.DataFrame(anchors_info)


    cur = conn.cursor()

    # 테이블 생성 (필요한 경우)
    create_table_query = '''
    CREATE TABLE IF NOT EXISTS anchors (
        anchor_id INTEGER PRIMARY KEY,
        alias TEXT,
        address TEXT,
        posX FLOAT,
        posY FLOAT,
        product_name TEXT,
        master TEXT
    )
    '''
    cur.execute(create_table_query)
    conn.commit()

    # 데이터 삽입
    for index, row in df.iterrows():
        insert_query = '''
        INSERT INTO anchors (anchor_id, alias, address, posX, posY, product_name, master)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (anchor_id) DO NOTHING
        '''
        cur.execute(insert_query, (
            row['Anchor Id'],
            row['Alias'],
            row['Address'],
            row['posX'],
            row['posY'],
            row['ProductName'],
            row['Master']
        ))
        conn.commit()

    # 연결 종료
    cur.close()
    conn.close()

    print("Data has been successfully saved to the PostgreSQL table.")
else:
    print(f"Failed to fetch data: {response.status_code}")
