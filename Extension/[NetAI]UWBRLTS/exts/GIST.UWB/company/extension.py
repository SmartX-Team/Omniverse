import omni.ext
import omni.ui as ui
from omni.usd import get_context
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf, PhysxSchema
import asyncio
import json
from aiokafka import AIOKafkaConsumer
import psycopg2
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import functools

# 스레드 풀 생성
db_thread_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="db_worker")

# 전역 변수
prim_map = {}
MAP_DATA = {}

# DB 작업을 위한 코루틴 변환 헬퍼 함수
async def run_in_thread(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(db_thread_pool, func, *args)

def db_connect():
    print("Attempting database connection...")
    config_path = "C:\\Users\\nuc\\Downloads\\config.json"
    print(f"Reading config from: {config_path}")
    
    try:
        with open(config_path, 'r') as file:
            config = json.load(file)
            print("Successfully loaded config file")
    except Exception as e:
        print(f"Error loading config file: {e}")
        return None

    try:
        conn = psycopg2.connect(
            dbname=config['postgres']['db_name'],
            user=config['postgres']['db_user'],
            password=config['postgres']['db_password'],
            host=config['postgres']['db_host'],
            port=config['postgres']['db_port']
        )
        print(f"Database connection established to {config['postgres']['db_host']}:{config['postgres']['db_port']}")
        return conn
    except Exception as e:
        print(f"Failed to connect to the database: {e}")
        return None

def record_timestamp_sync(tag_id, raw_timestamp, omniverse_timestamp):
    """동기적으로 DB에 타임스탬프를 기록하는 함수"""
    try:
        conn = db_connect()
        if not conn:
            print("Failed to connect to database for timestamp recording")
            return

        cursor = conn.cursor()
        insert_query = """
            INSERT INTO uwb_timestamp_tracking (tag_id, raw_timestamp, omniverse_timestamp)
            VALUES (%s, %s, %s)
        """
        cursor.execute(insert_query, (tag_id, raw_timestamp, omniverse_timestamp))
        conn.commit()
        print(f"Successfully recorded timestamps for tag {tag_id}")
    except Exception as e:
        print(f"Error recording timestamps to database: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

async def record_timestamp_to_db(tag_id, raw_timestamp):
    """비동기 래퍼 함수"""
    omniverse_timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    await run_in_thread(record_timestamp_sync, tag_id, raw_timestamp, omniverse_timestamp)

def fetch_map_data_sync():
    """동기적으로 매핑 데이터를 가져오는 함수"""
    conn = db_connect()
    if not conn:
        return {}

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT tag_id, nuc_id FROM uwb_tag")
        rows = cursor.fetchall()
        map_data = {str(row[0]): row[1] for row in rows}
        print(f"Successfully fetched {len(map_data)} mappings from database")
        return map_data
    except Exception as e:
        print(f"Failed to fetch data from the database: {e}")
        return {}
    finally:
        conn.close()

class CompanyHelloWorldExtension(omni.ext.IExt):
    def __init__(self):
        super().__init__()
        self.bootstrap_servers = '210.125.85.62:9094'
        self.topic_name = "omniverse-uwb"
        self._consumer = None
        self._group_id = "my--group"
        self._consuming_task = None
        self._map_update_task = None
        print(f"Extension initialized with Kafka broker: {self.bootstrap_servers}, topic: {self.topic_name}")

    async def initialize_data(self):
        """초기 데이터 로딩"""
        global prim_map, MAP_DATA
        
        # Stage 데이터 로딩
        stage = get_context().get_stage()
        print("Starting to build prim_map...")
        for prim in stage.Traverse():
            prim_map[prim.GetName()] = prim
        print(f"Finished building prim_map. Total prims: {len(prim_map)}")
        
        # DB 데이터 로딩
        MAP_DATA = await run_in_thread(fetch_map_data_sync)

    async def periodic_map_update(self):
        """주기적으로 매핑 데이터 업데이트"""
        while True:
            await asyncio.sleep(300)  # 5분마다 업데이트
            global MAP_DATA
            print("Updating mapping data from database...")
            MAP_DATA = await run_in_thread(fetch_map_data_sync)

    def on_startup(self, ext_id):
        print(f"[GIST.UWB.tracking] startup - Extension ID: {ext_id}")
        
        # 초기 데이터 로딩
        asyncio.ensure_future(self.initialize_data())
        
        # 주기적 업데이트 태스크 시작
        self._map_update_task = asyncio.ensure_future(self.periodic_map_update())
        
        self._window = ui.Window("UWB tracking", width=500, height=300)
        print("UWB tracking window created")

        with self._window.frame:
            with ui.VStack():
                async def on_click_coroutine():  
                     await self.start_consuming()

                def on_reset():
                    print("UWB tracking stopped by user")
                    if self._consuming_task:
                        self._consuming_task.cancel()
                        asyncio.run(self._consumer.stop())
                        self._consumer = None
                        print("Kafka consumer stopped and cleaned up")
   
                with ui.HStack():
                    ui.Button("UWB on", clicked_fn=lambda: asyncio.ensure_future(on_click_coroutine()))
                    ui.Button("UWB off", clicked_fn=on_reset)

    def on_shutdown(self):
        print("[company.hello.world] Extension shutdown initiated")
        if self._consumer:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self._consumer.stop())
            self._consumer = None
        if self._map_update_task:
            self._map_update_task.cancel()
        db_thread_pool.shutdown(wait=True)
        print("Shutdown completed")

    async def start_consuming(self):
        if self._consuming_task is None or self._consuming_task.done():
            self._consuming_task = asyncio.ensure_future(self.consume_messages())

    async def consume_messages(self):
        print("Initializing Kafka consumer...")
        self._consumer = AIOKafkaConsumer(
            self.topic_name,
            bootstrap_servers=self.bootstrap_servers,
            auto_offset_reset="earliest",
            group_id=self._group_id
        )
        await self._consumer.start()
        print(f"Kafka consumer started successfully - Topic: {self.topic_name}")
        try:
            async for msg in self._consumer:
                decoded_message = msg.value.decode('utf-8')
                # 메시지 처리를 별도의 태스크로 실행하여 consumer 블로킹 방지
                asyncio.create_task(process_message(decoded_message))
        except Exception as e:
            print(f"Error in Kafka consumer: {e}")
        finally:
            await self._consumer.stop()
            self._consumer = None
            print("Kafka consumer stopped")

async def process_message(decoded_message):
    """메시지 처리를 위한 별도 함수"""
    try:
        deserialized_data = json.loads(decoded_message)
        id_str = str(deserialized_data['id'])
        raw_timestamp = deserialized_data.get('raw_timestamp')
        name = MAP_DATA.get(id_str)
        
        if name is None:
            print(f"Warning: No mapping found for tag ID {id_str}")
            return

        x, z = await transform_coordinates(deserialized_data['latitude'], deserialized_data['longitude'])
        print(f"Transformed coordinates for {name} (ID: {id_str}): x={x}, z={z}")
        
        translation = [z, 105.0 if id_str == "15" else 90.0, x]
        print(f"Moving object {name} to position {translation}")
        
        # 오브젝트 이동과 타임스탬프 기록을 병렬로 처리
        await asyncio.gather(
            move_object_by_name(name, translation),
            record_timestamp_to_db(id_str, raw_timestamp)
        )
    except Exception as e:
        print(f"Error processing message: {e}")

async def transform_coordinates(x, y):
    m_x = (x) * 100
    m_y = (y) * -100
    return round(m_x, 2), round(m_y, 2)

async def move_object_by_name(obj_name, translation):
    if obj_name not in prim_map:
        print(f"Error: Object {obj_name} not found in prim_map")
        return
    
    prim = prim_map[obj_name]
    xformAPI = UsdGeom.XformCommonAPI(prim)
    xformAPI.SetTranslate(Gf.Vec3d(translation[0], translation[1], translation[2]))
    print(f"Successfully moved {obj_name} to position {translation}")