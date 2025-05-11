#해당 코드는 카프카 토픽으로 넘어온 LiDAR PointCloud2 메시지를 Delta Lake 기반 OTF 화 시켜 MINIO에 저장하는 예제
#실제 테스트는 아이작심에서 시뮬레이션으로 생성하는 LidAR PointCloud2 메시지를 저장했지만 로직상 실제 물리적 Husky UGV 에서 생성되는 LiDAR PointCloud2 메시지도 문제는 없음
# 데이터의 크기가 기본적으로 크니, 꼭 카프카 토픽에 저장 가능 용량 생각해서 전송할것; 예제 토픽은 3일 안에 토픽 내 저장된 데이터 지워지도록 설정함
#코드 배포는 메일이나 카톡으로 공유한 구글 드라이브내 사용 방법 참고하삼

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, current_timestamp, expr, to_json # udf 제거, 필요한 함수만 명시
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, BooleanType, LongType, ArrayType, TimestampType # ByteType 제거 (현재 스키마에서 미사용)
# from delta import configure_spark_with_delta_pip # SparkSession.builder에서 직접 설정 가능
from delta.tables import DeltaTable
import logging
import json


# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# config.json 파일에서 설정 읽기
config_path = '/mnt/ceph-pvc/config.json' # 실제 환경에 맞게 경로 수정 필요

try:
    with open(config_path, 'r') as config_file:
        config = json.load(config_file)

        # MinIO 설정
        minio_config = config['minio']
        minio_endpoint_url = minio_config['endpoint_url']
        minio_access_key = minio_config['access_key']
        minio_secret_key = minio_config['secret_key']
        minio_bucket_name = minio_config['bucket_name']

        # Kafka 설정
        # config.json에 'kafka' 섹션이 있고, 그 안에 'bootstrap.servers'가 있다고 가정합니다.
        # 만약 없다면 KeyError가 발생할 수 있으므로, 필요시 .get()으로 안전하게 접근하세요.
        kafka_bootstrap_servers = config['kafka']['bootstrap.servers']
        # LiDAR 전용 Kafka 토픽 읽기
        kafka_topic = config.get('lidar_kafka', {}).get('topic_name', 'omni-lidar')

        # Delta Lake 설정 (MinIO 경로)
        lidar_delta_config = config.get('lidar_delta', {})

        table_path_value = lidar_delta_config.get('table_name', 'delta-lidar-pointcloud-table')
        if table_path_value.startswith('s3a://'):
            delta_table_path = table_path_value
        else:
            delta_table_path = f"s3a://{minio_bucket_name}/{table_path_value}"

        checkpoint_path_value = lidar_delta_config.get('checkpoint_location', 'checkpoints-lidar')
        if checkpoint_path_value.startswith('s3a://'):
            checkpoint_path = checkpoint_path_value
        else:
            checkpoint_path = f"s3a://{minio_bucket_name}/{checkpoint_path_value}"
        
        # --- 설정값 확인 로깅 (중요) ---
        logger.info("--- LiDAR Application Configuration ---") # 수정: (pointcloud_to_kafka.py) 제거 또는 파일명 맞게 수정
        logger.info(f"Kafka Bootstrap Servers: {kafka_bootstrap_servers}")
        logger.info(f"LiDAR Kafka Topic: {kafka_topic}")
        logger.info(f"LiDAR Delta Table Path: {delta_table_path}")
        logger.info(f"LiDAR Checkpoint Path: {checkpoint_path}")
        logger.info(f"MinIO Endpoint: {minio_endpoint_url}")
        logger.info(f"S3A SSL Enabled for MinIO: {str(minio_endpoint_url.lower().startswith('https://')).lower()}")
        logger.info("-----------------------------------------------------------------")

except Exception as e:
    logger.error(f"Failed to load config file or parse configurations: {e}")
    raise

# MinIO 연결 정보 설정 (이미 위에서 minio_endpoint_url로 처리됨, minio_endpoint 변수는 Spark 설정에서 사용)
minio_endpoint = minio_endpoint_url 
use_ssl = minio_endpoint_url.lower().startswith("https://")

###################################
# 1. SparkSession 생성 (Delta Lake 및 S3A 설정 포함)
###################################
try:
    builder = SparkSession.builder \
        .appName("KafkaToDeltaLakeLiDAR") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.s3a.endpoint", minio_endpoint) \
        .config("spark.hadoop.fs.s3a.access.key", minio_access_key) \
        .config("spark.hadoop.fs.s3a.secret.key", minio_secret_key) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", str(use_ssl).lower()) \
        .config("spark.hadoop.fs.s3a.connection.ssl.trust-all-certificates", "true") 
        # .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") # 필요시 명시

    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN") 
    spark.conf.set("spark.databricks.delta.schema.autoMerge.enabled", "true")
    logger.info("SparkSession created successfully for LiDAR data processing.")
except Exception as e:
    logger.error("Failed to create SparkSession: %s", e)
    raise

###################################
# 2. PointCloud2 메시지 스키마 정의 (Kafka JSON 메시지 기준)
###################################
point_field_schema = StructType([
    StructField("name", StringType(), True),
    StructField("offset", IntegerType(), True),
    StructField("datatype", IntegerType(), True), 
    StructField("count", IntegerType(), True)
])

stamp_schema = StructType([
    StructField("sec", LongType(), True), 
    StructField("nanosec", LongType(), True) 
])

header_schema = StructType([
    StructField("stamp", stamp_schema, True),
    StructField("frame_id", StringType(), True)
])

pointcloud_json_schema = StructType([
    StructField("header", header_schema, True),
    StructField("height", IntegerType(), True),
    StructField("width", IntegerType(), True),
    StructField("fields", ArrayType(point_field_schema), True),
    StructField("is_bigendian", BooleanType(), True),
    StructField("point_step", IntegerType(), True),
    StructField("row_step", IntegerType(), True),
    StructField("data", StringType(), True), # Base64 인코딩된 문자열로 가정
    StructField("is_dense", BooleanType(), True)
])

# Delta Lake에 저장될 최종 스키마
delta_lidar_schema = StructType([
    StructField("capture_uuid", StringType(), False), 
    StructField("received_at", TimestampType(), False), 
    StructField("header_stamp_sec", LongType(), True),
    StructField("header_stamp_nanosec", LongType(), True),
    StructField("header_frame_id", StringType(), True),
    StructField("height", IntegerType(), True),
    StructField("width", IntegerType(), True),
    StructField("fields_json", StringType(), True), 
    StructField("is_bigendian", BooleanType(), True),
    StructField("point_step", IntegerType(), True),
    StructField("row_step", IntegerType(), True),
    StructField("point_data_base64", StringType(), True), 
    StructField("is_dense", BooleanType(), True)
    # 만약 kafka_timestamp도 저장하고 싶다면 여기에 StructField("kafka_timestamp", TimestampType(), True) 추가
])


###################################
# 3. Delta 테이블 초기화 (스키마 정의) - 필요시
###################################
try:
    if not DeltaTable.isDeltaTable(spark, delta_table_path):
        empty_df = spark.createDataFrame([], delta_lidar_schema)
        empty_df.write.format("delta").mode("overwrite").save(delta_table_path)
        logger.info(f"Initialized Delta table for LiDAR data at {delta_table_path} with schema.")
    else:
        logger.info(f"Delta table for LiDAR data already exists at {delta_table_path}.")
except Exception as e:
    logger.error(f"Failed to initialize/check Delta table for LiDAR: {e}")
    raise # 수정: 주석 해제하여 에러 발생 시 중단

###################################
# 4. Kafka에서 스트리밍 데이터 읽기
###################################
try:
    kafka_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", kafka_bootstrap_servers) \
        .option("subscribe", kafka_topic) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()
    logger.info(f"Successfully started reading from Kafka topic: {kafka_topic}")
except Exception as e:
    logger.error(f"Failed to read streaming data from Kafka: {e}")
    raise

###################################
# 5. foreachBatch 함수 정의 (LiDAR 데이터 파싱 및 Delta Lake 저장)
###################################
def process_lidar_batch(batch_df, batch_id):
    # from pyspark.sql.functions import from_json, col, current_timestamp, expr, to_json # 이미 전역으로 임포트됨

    logger.info(f"[Batch {batch_id}] Processing new micro-batch...")

    if batch_df.isEmpty(): # 수정: batch_df.count() == 0 보다 batch_df.isEmpty()가 더 효율적일 수 있음
        logger.info(f"[Batch {batch_id}] Empty batch, skipping.")
        return

    parsed_df = batch_df.select(
        from_json(col("value").cast("string"), pointcloud_json_schema).alias("pc_data"),
        col("timestamp").alias("kafka_timestamp") # Kafka 메시지 자체의 타임스탬프
    )

    # pc_data가 null인 경우 (JSON 파싱 실패)를 제외하고 처리 (선택 사항, 데이터 품질에 따라 결정)
    # parsed_df = parsed_df.filter(col("pc_data").isNotNull())

    processed_df = parsed_df.select(
        expr("uuid()").alias("capture_uuid"), 
        current_timestamp().alias("received_at"), 
        col("pc_data.header.stamp.sec").alias("header_stamp_sec"),
        col("pc_data.header.stamp.nanosec").alias("header_stamp_nanosec"),
        col("pc_data.header.frame_id").alias("header_frame_id"),
        col("pc_data.height").alias("height"),
        col("pc_data.width").alias("width"),
        to_json(col("pc_data.fields")).alias("fields_json"), 
        col("pc_data.is_bigendian").alias("is_bigendian"),
        col("pc_data.point_step").alias("point_step"),
        col("pc_data.row_step").alias("row_step"),
        col("pc_data.data").alias("point_data_base64"), 
        col("pc_data.is_dense").alias("is_dense")
        # kafka_timestamp는 여기서 선택하지만, delta_lidar_schema에 없으면 최종 저장 시 제외됨 (아래에서 명시적으로 선택)
    )

    final_df_to_write = processed_df.filter(col("header_frame_id").isNotNull())

    if not final_df_to_write.isEmpty(): # 수정: count() > 0 보다 isEmpty() 사용
        logger.info(f"[Batch {batch_id}] Writing {final_df_to_write.count()} valid records to Delta Lake table: {delta_table_path}")
        try:
            # delta_lidar_schema에 정의된 컬럼만 선택하여 저장
            columns_for_delta = [field.name for field in delta_lidar_schema.fields]
            df_to_save = final_df_to_write.select(*columns_for_delta) # 수정: *를 사용하여 컬럼 목록 전달

            df_to_save.write \
                .format("delta") \
                .mode("append") \
                .option("mergeSchema", "true") \
                .save(delta_table_path)
            logger.info(f"[Batch {batch_id}] Successfully wrote data to Delta Lake.")
        except Exception as e_write:
            logger.error(f"[Batch {batch_id}] Error writing to Delta Lake: {e_write}")
            # 여기서도 raise e_write를 고려할 수 있으나, 배치 실패가 전체 스트림을 중단시킬지 여부는 정책에 따라 결정
    else:
        logger.info(f"[Batch {batch_id}] No valid records to write after parsing and filtering.")


###################################
# 6. 스트리밍 쿼리 실행
###################################
try:
    query = kafka_df.writeStream \
        .foreachBatch(process_lidar_batch) \
        .option("checkpointLocation", checkpoint_path) \
        .trigger(processingTime="30 seconds")  \
        .start()
    logger.info(f"Started writing streaming LiDAR data from Kafka topic '{kafka_topic}' to Delta Lake on MinIO at '{delta_table_path}'")
except Exception as e:
    logger.error(f"Failed to start streaming query for LiDAR data: {e}")
    raise

###################################
# 7. 스트리밍 대기 (종료 방지)
###################################
try:
    query.awaitTermination()
except KeyboardInterrupt:
    logger.info("Streaming query terminated by user (KeyboardInterrupt).")
except Exception as e:
    logger.error(f"Error during LiDAR streaming query execution: {e}")
    # 여기서도 raise를 고려할 수 있지만, 일반적으로 스트림은 최대한 계속 실행되도록 두는 경우가 많습니다.
finally:
    logger.info("Stopping SparkSession for LiDAR processing.")
    spark.stop()
    logger.info("SparkSession stopped.")
    
