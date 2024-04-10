import omni.ext
import omni.ui as ui
from omni.usd import get_context
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf, PhysxSchema
import asyncio
import json
from aiokafka import AIOKafkaConsumer

prim_map = {}
stage = get_context().get_stage()
# stage에서 모든 prim들을 순회하며 hashmap에 저장
for prim in stage.Traverse():
    prim_map[prim.GetName()] = prim

# 하드코딩한 ID 와 NUC_PC 이름 매핑
MAP_DATA = {
    "24":"NUC11_01",
    "40":"NUC11_02",
    "39":"NUC11_03",
    "37":"NUC11_04",
    "36":"NUC11_05",
    "31":"NUC11_06",
    "49":"NUC11_07",
    "25":"NUC11_08",
    "44":"NUC11_09",
    "23":"NUC11_10",
    "20":"NUC12_01",
    "22":"NUC12_02",
    "46":"NUC12_03",
    "19":"NUC12_04",
    "45":"NUC12_05",
    "29":"NUC12_06",
    "18":"NUC12_07",
    "33":"NUC12_08",
    "43":"NUC12_09",
    "26":"NUC12_10",
    "48":"NUC12_11",
    "41":"NUC12_12",
    "21":"NUC12_13",
    "35":"NUC12_14",
    "47":"NUC12_15",
    "38":"NUC12_16",
    "9":"NUC12_17",
    "34":"NUC12_18",
    "32":"NUC12_19",
    "42":"NUC12_20",
    "15":"HUSKY_01"
}

class CompanyHelloWorldExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.
    def __init__(self):

        self.bootstrap_servers = "10.32.187.108:9092"
        self.topic_name = "test"
        self._group_id = "my--group"
        self._consumer = None
        self._consuming = False

    def on_startup(self, ext_id):
        print("[GIST.UWB.traking] startup")
        #asyncio.ensure_future(self.consume_messages())

        self._window = ui.Window("UWB traking", width=500, height=300)
        with self._window.frame:
            with ui.VStack():


                async def on_click_coroutine():  
                     asyncio.create_task(self.consume_messages())

                def on_reset():
                    print("UWB off")
                    asyncio.run(self._consumer.stop()) if self._consumer else None
   
                with ui.HStack():
                    ui.Button("UWB on", clicked_fn=lambda: asyncio.ensure_future(on_click_coroutine()))
                    ui.Button("UWB off", clicked_fn=on_reset)

    def on_shutdown(self):
        print("[company.hello.world] company hello world shutdown")
        #asyncio.run(self._consumer.stop()) if self._consumer else None
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._consumer.stop()) if self._consumer else None

    async def consume_messages(self):
        self._consumer = AIOKafkaConsumer(
            self.topic_name,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self._group_id,
            auto_offset_reset="earliest"
        )
            # Start the consumer
        await self._consumer.start()
        try:
            # Consume messages
            async for msg in self._consumer:

                decoded_message = msg.value.decode('utf-8')
                await move_object_byKafka(decoded_message)
        finally:
            # Will leave consumer group; perform autocommit if enabled.
            await self._consumer.stop()

async def move_object_byKafka(data):
    deserialized_data = json.loads(data)

    id_str = str(deserialized_data['id'])
    name = MAP_DATA.get(id_str)
    #print(deserialized_data)
    x, z = await transform_coordinates(deserialized_data['latitude'], deserialized_data['longitude'])
    #obj_name = deserialized_data['alias'].replace('/', '_')
    if id_str == "15":
        translation = [z, 105.0, x]
    else:
        translation = [z, 90.0, x] 
    await move_object_by_name(name, translation)

async def transform_coordinates(x, y):
  
    m_x = (x) *100
    m_y = (y) *100
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
    else :
        prim = prim_map[obj_name]
        xformAPI = UsdGeom.XformCommonAPI(prim)
        xformAPI.SetTranslate(Gf.Vec3d(translation[0], translation[1], translation[2]))