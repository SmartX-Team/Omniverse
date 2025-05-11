# OTF(Deltalake) 로 저장된 PointCloud 데이터를 원하는 시간대에 맞춰 가져온뒤 복호화하는 예제
# 실제 아이작심 RTX Sensor SDK 시뮬레이션을 통해 생성된 포인트 클라우드 데이터가 인코딩(전송) -> OTF -> 복호화를 진행해도 깨지지 않는지 검증하려고 사용한 예제 코드임
# 결과적으로는 문제 없이 복호화되는건 확인했는데, 실 사용에서 OTF Time Travel 기능은 TIMESTAMP_AS_OF 옵션 말고 SQL 문 작성해서 사용하기를 추천 

import json
import base64
import struct # 바이너리 데이터(포인트 클라우드) 해석을 위해 필요
from pyspark.sql import SparkSession
from delta import configure_spark_with_delta_pip

# --- 사용자 설정 필요한 부분 ---
MINIO_ENDPOINT_URL = 'http://10.79.1.0:9000'  # 실제 MinIO 엔드포인트 URL
MINIO_ACCESS_KEY = 'YYFfYYBbYyGREfMIU2oI'    # MinIO Secret Key /내부망이여도 보안상 지움, Filebrowser 나 Minio 페이지가면 다 볼 수 있음
MINIO_SECRET_KEY = '0ddqNkGrdKI46x5MYq5gEPYqfFgqsycAQiOBHH73'  #  MinIO Secret Key /내부망이여도 보안상 지움, 
# DELTA_TABLE_PATH는 Spark 스트리밍 작업에서 사용한 경로와 동일해야함
# 예: "s3a://your-minio-bucket/delta-lidar-pointcloud-table"
DELTA_TABLE_PATH = 's3a://twin-bucket/delta-omni-lidar-tables' # 실제 Delta 테이블 경로

# 시간 여행(Time Travel) 파라미터 (둘 중 하나 또는 모두 None으로 설정 가능)
# 특정 시점의 스냅샷을 보려면 ISO 8601 형식의 문자열 사용
#TIMESTAMP_AS_OF = "2025-05-11 18:15:00" # !!!!!! 실제 조회하고 싶은 시간으로 변경 ;
TIMESTAMP_AS_OF = None # 가장 최신 데이터 기준 조회 ; 
# VERSION_AS_OF = None                 # 또는 특정 버전 번호를 사용하려면 이 값을 설정 

# (선택 사항) 특정 capture_uuid의 메시지만 디코딩하려면 여기에 UUID 문자열을 입력
# None으로 두면 아래 NUM_MESSAGES_TO_DECODE 만큼의 메시지를 가져옵니다.
TARGET_CAPTURE_UUID = None # 예: "a1b2c3d4-e5f6-7890-1234-567890abcdef"

# TARGET_CAPTURE_UUID가 None일 경우, 가져와서 디코딩할 메시지 수
NUM_MESSAGES_TO_DECODE = 2
# --- 사용자 설정 종료 ---

# sensor_msgs/PointField.datatype 상수값
DATATYPE_INT8    = 1
DATATYPE_UINT8   = 2
DATATYPE_INT16   = 3
DATATYPE_UINT16  = 4
DATATYPE_INT32   = 5
DATATYPE_UINT32  = 6
DATATYPE_FLOAT32 = 7
DATATYPE_FLOAT64 = 8

def get_struct_format(datatype, count):
    """PointField.datatype에 따른 struct 모듈 포맷 문자와 크기를 반환"""
    if datatype == DATATYPE_INT8:    return f'{count}b', 1 * count
    if datatype == DATATYPE_UINT8:   return f'{count}B', 1 * count
    if datatype == DATATYPE_INT16:   return f'{count}h', 2 * count
    if datatype == DATATYPE_UINT16:  return f'{count}H', 2 * count
    if datatype == DATATYPE_INT32:   return f'{count}i', 4 * count
    if datatype == DATATYPE_UINT32:  return f'{count}I', 4 * count
    if datatype == DATATYPE_FLOAT32: return f'{count}f', 4 * count
    if datatype == DATATYPE_FLOAT64: return f'{count}d', 8 * count
    return None, 0

def decode_pointcloud_data(msg_dict):
    """Delta Lake에서 읽은 dict로부터 PointCloud2 데이터를 디코딩하여 일부 포인트를 추출"""
    try:
        header = msg_dict.get('header', {})
        frame_id = header.get('frame_id', 'N/A')
        stamp_sec = header.get('stamp', {}).get('sec', 0)
        stamp_nanosec = header.get('stamp', {}).get('nanosec', 0)

        print(f"\n--- Decoded PointCloud from Delta Lake ---")
        print(f"Frame ID: {frame_id}, Timestamp: {stamp_sec}.{stamp_nanosec:09d}")
        print(f"Dimensions: Height={msg_dict.get('height')}, Width={msg_dict.get('width')}")
        print(f"Point Step: {msg_dict.get('point_step')}, Row Step: {msg_dict.get('row_step')}")
        
        is_bigendian_msg = msg_dict.get('is_bigendian', False) # is_bigendian 값 가져오기
        endian_prefix = '>' if is_bigendian_msg else '<' # 엔디안 문자 설정

        print(f"Is Bigendian: {is_bigendian_msg} (Endian prefix for unpack: '{endian_prefix}')")
        print(f"Is Dense: {msg_dict.get('is_dense')}")

        fields = msg_dict.get('fields', []) # fields_json이 파싱된 리스트
        point_step = msg_dict.get('point_step', 0)
        
        # Base64 디코딩하여 원본 바이너리 데이터 복원
        binary_data = base64.b64decode(msg_dict.get('data', '')) # data는 point_data_base64 값

        if not fields or point_step == 0 or not binary_data:
            print("PointCloud data is incomplete or fields/point_step is missing.")
            return

        field_info = {}
        print("Field details:")
        for field_obj in fields: # Spark DataFrame에서 읽을 때는 이미 dict의 리스트일 수 있음
            field_name = field_obj['name']
            fmt_char, size = get_struct_format(field_obj['datatype'], field_obj['count'])
            if fmt_char:
                field_info[field_name] = {
                    'offset': field_obj['offset'], 
                    'format': endian_prefix + fmt_char, # 엔디안 적용된 포맷
                    'raw_format': fmt_char, # 원본 포맷 문자 (디버깅용)
                    'size': size, 
                    'datatype': field_obj['datatype']
                }
                print(f"  - Name: {field_name}, Offset: {field_obj['offset']}, Datatype: {field_obj['datatype']}, Count: {field_obj['count']}, Detected Format: {field_info[field_name]['format']}")

        if not all(f in field_info for f in ['x', 'y', 'z']):
            print("Warning: Could not find x, y, or z fields in PointCloud2.")
            return

        num_points_to_print = min(5, msg_dict.get('width', 0) * msg_dict.get('height', 0))
        print(f"Decoding first {num_points_to_print} points:")

        for i in range(num_points_to_print):
            point_start_offset = i * point_step
            
            try:
                point_values = {}
                all_required_fields_float32 = True
                for f_name in ['x', 'y', 'z']: # 주요 필드 확인
                    if field_info[f_name]['datatype'] != DATATYPE_FLOAT32:
                        all_required_fields_float32 = False
                        break
                
                if not all_required_fields_float32:
                    print(f"  Point {i}: x, y, z fields are not all FLOAT32. Skipping detailed decoding.")
                    # 필요한 경우 다른 타입에 대한 처리 추가
                    continue

                x_val = struct.unpack_from(field_info['x']['format'], binary_data, point_start_offset + field_info['x']['offset'])[0]
                y_val = struct.unpack_from(field_info['y']['format'], binary_data, point_start_offset + field_info['y']['offset'])[0]
                z_val = struct.unpack_from(field_info['z']['format'], binary_data, point_start_offset + field_info['z']['offset'])[0]
                
                print(f"  Point {i}: x={x_val:.3f}, y={y_val:.3f}, z={z_val:.3f}", end="")

                # 다른 필드 (예: intensity)도 있다면 유사하게 추출 가능
                if 'intensity' in field_info:
                    # intensity의 실제 포맷을 사용해야 함 (예시에서는 FLOAT32 가정)
                    if field_info['intensity']['datatype'] == DATATYPE_FLOAT32:
                        intensity_val = struct.unpack_from(field_info['intensity']['format'], binary_data, point_start_offset + field_info['intensity']['offset'])[0]
                        print(f", intensity={intensity_val:.3f}", end="")
                
                print() # Newline after each point

            except struct.error as e:
                print(f"  Error decoding point {i}: {e}. Possibly offset issue, data corruption, or incorrect format string for endianness ({endian_prefix}).")
                break
            except IndexError:
                print(f"  Error accessing data for point {i}. Possibly not enough data bytes.")
                break
        
        if num_points_to_print == 0:
            print("No points to decode (width or height is 0).")

    except Exception as e:
        print(f"Error during PointCloud data decoding: {e}")


def main():
    # PySpark 3.5.0은 Scala 2.12를 사용합니다. 오류 로그에서 delta-spark_2.12;3.3.1 확인.
    # 해당 버전에 맞춰 Delta Lake 패키지를 명시합니다.
    DELTA_VERSION = "3.3.1"
    SCALA_VERSION = "2.12" # PySpark 버전에 일반적으로 맞춰짐

    # 필요한 모든 패키지를 여기에 나열합니다.
    EXTRA_PACKAGES = ",".join([
        f"io.delta:delta-spark_{SCALA_VERSION}:{DELTA_VERSION}", # Delta Lake 패키지
        "org.apache.hadoop:hadoop-aws:3.3.4",                 # S3A 커넥터
        "com.amazonaws:aws-java-sdk-bundle:1.12.586"          # AWS SDK
    ])

    builder = (
        SparkSession.builder.appName("DeltaPointCloudDecoder")
        # Delta 확장 및 카탈로그 설정
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        # ▶▶ 수정: 필요한 모든 JAR을 spark.jars.packages를 통해 자동 다운로드
        .config("spark.jars.packages", EXTRA_PACKAGES)
        # 권장: Delta + S3A 전용 WAL 구현
        .config("spark.delta.logStore.class", "org.apache.spark.sql.delta.storage.S3SingleDriverLogStore")
        # S3A (MinIO) 설정
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT_URL)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled",
                str(MINIO_ENDPOINT_URL.lower().startswith("https://")).lower())
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
    )

    # ▶▶ 수정: configure_spark_with_delta_pip() 호출 대신 builder에서 직접 getOrCreate() 호출
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN") # Spark 로그 레벨 조정

    print(f"SparkSession created. Reading Delta table: {DELTA_TABLE_PATH}")

    try:
        delta_reader = spark.read.format("delta")

        if TIMESTAMP_AS_OF:
            print(f"Attempting to read data as of timestamp: {TIMESTAMP_AS_OF}")
            delta_reader = delta_reader.option("timestampAsOf", TIMESTAMP_AS_OF)
        # elif VERSION_AS_OF is not None: # VERSION_AS_OF를 사용하지 않으므로 주석 처리
        #     print(f"Attempting to read data as of version: {VERSION_AS_OF}")
        #     delta_reader = delta_reader.option("versionAsOf", str(VERSION_AS_OF))
        else:
            print("Reading latest version of the Delta table.")

        df = delta_reader.load(DELTA_TABLE_PATH)

        print("Delta table schema:")
        df.printSchema()

        if TARGET_CAPTURE_UUID:
            print(f"Filtering for capture_uuid: {TARGET_CAPTURE_UUID}")
            df_to_process = df.filter(f"capture_uuid = '{TARGET_CAPTURE_UUID}'")
            count = df_to_process.count()
            if count == 0:
                print(f"No data found for capture_uuid: {TARGET_CAPTURE_UUID} at the specified time/version.")
                spark.stop() # 세션 종료 추가
                return
            print(f"Found {count} record(s) for capture_uuid: {TARGET_CAPTURE_UUID}")
        else:
            print(f"No specific capture_uuid provided. Taking first {NUM_MESSAGES_TO_DECODE} message(s).")
            df_to_process = df.limit(NUM_MESSAGES_TO_DECODE)
            if df_to_process.isEmpty(): # isEmpty()는 DataFrame API에 직접 없음. count() == 0 사용
                if df_to_process.count() == 0:
                    print(f"No data found in the table (or specified snapshot) to decode.")
                    spark.stop() # 세션 종료 추가
                    return

        # df_to_process.count()가 0이 아닌 경우에만 다음 단계 진행 (위에서 이미 처리됨)
        print(f"Processing {df_to_process.count()} message(s)...")
        for row in df_to_process.collect():
            try:
                fields_list = json.loads(row.fields_json)
            except json.JSONDecodeError as e:
                print(f"Error parsing fields_json for capture_uuid {row.capture_uuid}: {e}")
                print(f"Problematic fields_json string: {row.fields_json}")
                continue

            msg_dict = {
                "header": {
                    "stamp": {
                        "sec": row.header_stamp_sec,
                        "nanosec": row.header_stamp_nanosec
                    },
                    "frame_id": row.header_frame_id
                },
                "height": row.height,
                "width": row.width,
                "fields": fields_list,
                "is_bigendian": row.is_bigendian,
                "point_step": row.point_step,
                "row_step": row.row_step,
                "data": row.point_data_base64,
                "is_dense": row.is_dense
            }

            if row.capture_uuid:
                 print(f"--- Decoding message with capture_uuid: {row.capture_uuid} ---")
            decode_pointcloud_data(msg_dict)

    except Exception as e:
        print(f"An error occurred while reading from Delta Lake or processing data: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print("Stopping SparkSession.")
        spark.stop()

if __name__ == '__main__':
    main()