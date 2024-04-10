import omni.ext
import omni.ui as ui
from omni.usd import get_context
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf, PhysxSchema
import asyncio
import json
from aiokafka import AIOKafkaConsumer


# prim path to material mapping
MAP_DATA = {
    "0948":"HUSKY_02",
    "0950":"HUSKY_01",
}
#
obj_name = "/World/HUSKY_01"
stage = get_context().get_stage()
prim = stage.GetPrimAtPath(obj_name)
#Currently, we are only receiving IMU data from ROS, and we are tentatively ensuring a continuous flow of communication.
class GistRosExtension(omni.ext.IExt):


    def __init__(self):

        self.bootstrap_servers = "10.32.187.108:9092"
        self.topic_name = "ros_test"
        self._group_id = "my--group"
        self._consumer = None
        self._consuming = False

    def on_startup(self, ext_id):
        print("[gist.ros] gist ros startup")
        #nest_asyncio.apply()
        async def on_click_coroutine():  
            asyncio.create_task(self.consume_messages())
        self._count = 0

        self._window = ui.Window("My Window", width=300, height=300)
        with self._window.frame:
            with ui.VStack():
                label = ui.Label("")


                def on_click():
                    self._count += 1
                    label.text = f"count: {self._count}"

                def on_reset():
                    self._count = 0
                    label.text = "empty"

                on_reset()

                with ui.HStack():
                    ui.Button("ROS on", clicked_fn=lambda: asyncio.ensure_future(on_click_coroutine()))
                    ui.Button("Reset", clicked_fn=on_reset)

    def on_shutdown(self):
        print("[gist.ros] gist ros shutdown")
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
                json_message = json.loads(decoded_message)
                #print(f"Consumed message: {decoded_message}")
                #print(f"Consumed message: {json_message['robot_name']}")
                #print(f"Consumed message: {json_message['azimuth_angle_degrees']}")
                await rotate_object_byKafka(json_message)
        finally:
            # Will leave consumer group; perform autocommit if enabled.
            await self._consumer.stop()


async def rotate_object_byKafka(data):

    #id_str = str(data['robot_name'])
    #name = MAP_DATA.get(id_str)
    
    rotation_attr = prim.GetAttribute('xformOp:rotateXYZ')
    rotation_value = rotation_attr.Get()

    omniverse_data = data['azimuth_angle_degrees']-55
    if omniverse_data < 0:
        omniverse_data = omniverse_data + 360
    omniverse_data = omniverse_data + 180
    rotation = [rotation_value[0], omniverse_data, rotation_value[2]]  # Move 10 units in X and 5 units in Z
    rotation_attr = prim.GetAttribute('xformOp:rotateXYZ').Set(Gf.Vec3d(rotation), 0)
