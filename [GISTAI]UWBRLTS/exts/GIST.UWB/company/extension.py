"""
MobileX K8S Cluster 로 전체적인 인프라 구성을 옮겼으므로 환경 설정이 어느 정도 안정화된거 같아
기존 하드코딩한 매핑 데이터 부분은 DB에서 읽어도록 수정해둠

"""

import omni.ext
import omni.ui as ui
from omni.usd import get_context
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf, PhysxSchema
import asyncio
import json
from aiokafka import AIOKafkaConsumer
import psycopg2

prim_map = {}
stage = get_context().get_stage()
# stage에서 모든 prim들을 순회하며 hashmap에 저장
for prim in stage.Traverse():
    prim_map[prim.GetName()] = prim

# 기존 하드코딩 제거하고 DB에서 매핑 정보가져오도록 수정 해둠
# Database connection function
def db_connect():
    
    # Check the directory where the config file is located
    config_path = "C:\\Users\\nuc\\Downloads\\config.json"
    with open(config_path, 'r') as file:
        config = json.load(file)

    try:
        conn = psycopg2.connect(
            dbname=config['postgres']['db_name'],
            user=config['postgres']['db_user'],
            password=config['postgres']['db_password'],
            host=config['postgres']['db_host'],
            port=config['postgres']['db_port']
        )
        print("Database connection successfully established.")
        return conn
    except Exception as e:
        print(f"Failed to connect to the database: {e}")
        return None

# Function to fetch data from uwb_tag table and update MAP_DATA
def fetch_and_update_map_data(conn):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT tag_id, nuc_id FROM uwb_tag")
        rows = cursor.fetchall()
        map_data = {str(row[0]): row[1] for row in rows}
        print("MAP_DATA successfully updated from database.")
        return map_data
    except Exception as e:
        print(f"Failed to fetch data from the database: {e}")
        return {}

# Connect to the database and update MAP_DATA
conn = db_connect()
if conn:
    MAP_DATA = fetch_and_update_map_data(conn)
    conn.close()

class CompanyHelloWorldExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.
    def __init__(self):
        super().__init__()
        self.bootstrap_servers = '210.125.85.62:9094'
        self.topic_name = "omniverse-uwb"
        self._consumer = None
        self._group_id = "my--group"
        self._consuming_task = None

    def on_startup(self, ext_id):
        print("[GIST.UWB.traking] startup")
        #asyncio.ensure_future(self.consume_messages())

        self._window = ui.Window("UWB traking", width=500, height=300)
        with self._window.frame:
            with ui.VStack():
                async def on_click_coroutine():  
                     await self.start_consuming()

                def on_reset():
                    print("UWB off")
                    if self._consuming_task:
                        self._consumer_task.cancel()
                        asyncio.run(self._consumer.stop())
                        self._consumer = None
   
                with ui.HStack():
                    ui.Button("UWB on", clicked_fn=lambda: asyncio.ensure_future(on_click_coroutine()))
                    ui.Button("UWB off", clicked_fn=on_reset)

    def on_shutdown(self):
        print("[company.hello.world] company hello world shutdown")
        #asyncio.run(self._consumer.stop()) if self._consumer else None
        if self._consumer:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self._consumer.stop())
            self._consumer = None

    async def start_consuming(self):
        if self._consuming_task is None or self._consuming_task.done():
            self._consuming_task = asyncio.ensure_future(self.consume_messages())

    async def consume_messages(self):
        print("UWB on")
        self._consumer = AIOKafkaConsumer(
            self.topic_name,
            bootstrap_servers=self.bootstrap_servers,
            auto_offset_reset="earliest",
            group_id=self._group_id
        )
            # Start the consumer
        await self._consumer.start()
        try:
            # Consume messages
            async for msg in self._consumer:
                decoded_message = msg.value.decode('utf-8')
                await _process_kafka_message(decoded_message)
        finally:
            # Will leave consumer group; perform autocommit if enabled.
            await self._consumer.stop()
            self._consumer = None

async def _process_kafka_message(data):
    deserialized_data = json.loads(data)
    id_str = str(deserialized_data['id'])
    name = MAP_DATA.get(id_str)

    x, z = await transform_coordinates(deserialized_data['latitude'], deserialized_data['longitude'])
    #obj_name = deserialized_data['alias'].replace('/', '_')
    print(f"Object {name} is moving to {x}, {z}")
    if id_str == "15":
        translation = [z, 105.0, x]
    else:
        translation = [z, 90.0, x] 
    await move_object_by_name(name, translation)

async def transform_coordinates(x, y):
    m_x = (x) *100
    m_y = (y) *-100
    x_prime = round(m_x, 2)
    z_prime = round(m_y, 2)

    return x_prime, z_prime

async def move_object_by_name(obj_name, translation):
    """
    Move an object by its name in Omniverse.

    Parameters:
    - obj_name (str): The name of the object.
    - translation (list): A list containing the x, y, and z translation values.
    """
    # Fetch the object using its name
    if obj_name not in prim_map:
        print(f"Object {obj_name} not found.")
        return
    
    prim = prim_map[obj_name]
    xformAPI = UsdGeom.XformCommonAPI(prim)
    xformAPI.SetTranslate(Gf.Vec3d(translation[0], translation[1], translation[2]))