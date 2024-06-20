import omni.ext
import omni.ui as ui
from omni.usd import get_context
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf, PhysxSchema
import asyncio
from aiokafka import AIOKafkaConsumer
import pickle
import math
import json

obj_name = "/World/HUSKY_01"
stage = get_context().get_stage()
prim = stage.GetPrimAtPath(obj_name)

human_obj_name = "/World/human01" 
human_prim = stage.GetPrimAtPath(human_obj_name)

color_path = {
    "Red": "/World/Looks/poweroff",
    "Yellow": "/World/Looks/logout",
    "Green": "/World/Looks/poweron",
    "Gray": "/World/Looks/default"
    }

prim_paths = ["/World/human_01", "/World/human_02", "/World/human_03"]

class GistLidarExtension(omni.ext.IExt):
    def __init__(self):
        self._window = None
        self._consumer_task = None
        self._loop = asyncio.get_event_loop()
        self._count = 0
        self.consumer = None
        self.color_path = color_path
        self.human_prim_list = self._initialize_prims(prim_paths)
        self.max_count = len(self.human_prim_list)
    def _initialize_prims(self, prim_paths):
        """
        주어진 경로의 프림들을 초기화하고 저장
        :param prim_paths: 프림 경로 리스트
        :return: 프림 경로에 대한 프림 객체 리스트
        """
        prim_list = []
        for path in prim_paths:
            prim = stage.GetPrimAtPath(path)
            if prim.IsValid():
                prim_list.append(prim)
            else:
                print(f"Prim not found at path: {path}")
        return prim_list

    def on_startup(self, ext_id):

        # UI 창 생성
        self._window = ui.Window("Gist Lidar", width=300, height=300)
        with self._window.frame:
            with ui.VStack():
                
                def on_reset():
                    self._count = 0

                on_reset()

                with ui.HStack():
                    ui.Button("Lidar on", clicked_fn=lambda: asyncio.ensure_future(self.start_consumer()))
                    ui.Button("Reset", clicked_fn=on_reset)

    def on_shutdown(self):
        print("[gist.lidar] gist lidar shutdown")
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                self._loop.run_until_complete(self._consumer_task)
            except asyncio.CancelledError:
                pass
            self._consumer_task = None
        if self.consumer:
            self._loop.run_until_complete(self.consumer.stop())
            self.consumer = None

    async def start_consumer(self):
        if self._consumer_task is None or self._consumer_task.done():
            self._consumer_task = asyncio.create_task(self.consume())

    async def consume(self):
        # Kafka Consumer 설정
        self.consumer = AIOKafkaConsumer(
            'lidar_dect_result',  # 수신할 Kafka 토픽
            bootstrap_servers=['10.32.187.108:9092'],  # Kafka 브로커 주소
            value_deserializer=lambda v: pickle.loads(v),  
            auto_offset_reset="earliest"
        )

        # Kafka Consumer 시작
        await self.consumer.start()
        print("Kafka Consumer for lidar_dect_result is running...")

        try:
            # Kafka 메시지 수신 및 처리
            async for message in self.consumer:
                
                json_string = message.value

                try:
                    detection_results = json.loads(json_string)
                except json.JSONDecodeError:
                    print("Failed to decode JSON")
                    continue

                print(detection_results)

                # 데이터가 없다는 메시지 확인
                if all('bbox' in dr and len(dr['bbox']) == 0 for dr in detection_results):
                    print("No detections found. Hiding all prims.")
                    self.update_visibility_based_on_data([])
                    continue

                self.update_visibility_based_on_data(detection_results)

                # Human Detection Count
                human_count = 0

                # 리스트를 순회하여 각 검출 결과를 처리
                for detection_result in detection_results:

                    if human_count >= len(self.human_prim_list):
                        print(f"Human count {human_count} exceeded max count {len(self.human_prim_list)}")
                        break

                    if 'bbox' in detection_result:
                        centroid_x, centroid_y, centroid_z = self.calculate_centroid(detection_result['bbox'])

                        prim_position = self.get_prim_position()

                        move_x = prim_position[0] + centroid_x * 15
                        move_y = prim_position[2] + centroid_y * 15

                        if centroid_x < 0:
                            move_x -= 50
                        else:
                            move_x += 50

                        if centroid_y < 0:
                            move_y -= 50
                        else:
                            move_y += 50


                        
                        self.move_object_byKafka(move_x, move_y, self.human_prim_list[human_count] )
                        
                        distance = self.calculate_distance(prim_position, (centroid_x, centroid_y, centroid_z))
                        self.change_material(detection_result['score'], distance, self.human_prim_list[human_count])

                        human_count += 1
        except asyncio.CancelledError:
            print("Consumer task was cancelled.")
        finally:
            # Kafka Consumer 종료
            await self.consumer.stop()
            print("Kafka Consumer stopped.")

    def calculate_centroid(self, bbox):
        # bbox는 8개의 3D 좌표를 포함하는 리스트
        x_coords = [point[0] for point in bbox]
        y_coords = [point[1] for point in bbox]
        z_coords = [point[2] for point in bbox]

        centroid_x = sum(x_coords) / len(x_coords)
        centroid_y = sum(y_coords) / len(y_coords)
        centroid_z = sum(z_coords) / len(z_coords)

        return centroid_x, centroid_y, centroid_z

    def get_prim_position(self):

        if not prim:
            print(f"Prim not found at path")
            return None
        
        # xformOp:translate 속성에서 위치를 추출
        translate_attr = prim.GetAttribute('xformOp:translate')
        if not translate_attr.IsValid():
            print(f"Translate attribute not found for prim at path")
            return None

        translate_value = translate_attr.Get()
        return translate_value
    
    def move_object_byKafka(self, x, z, human_prim):

        translation = [x, 91, z]

        xformAPI = UsdGeom.XformCommonAPI(human_prim)
        xformAPI.SetTranslate(Gf.Vec3d(translation[0], translation[1], translation[2]))

    def change_material(self, score, distance, human_prim):

        if score < 20 and distance < 5:
            color = "Yellow"
        elif score < 20 and distance > 5:
            color = "Gray"
        elif score >= 20 and distance > 5:
            color = "Green"
        else:
            color = "Red"  # 기본 색상 설정 또는 다른 조건 추가 가능

        material = UsdShade.Material.Get(stage, self.color_path[color])
        material_binding_api = UsdShade.MaterialBindingAPI.Apply(human_prim)
        material_binding_api.Bind(material)

    def calculate_distance(self, prim_position, centroid):
        # 유클리드 거리 계산
        return math.sqrt(
            (centroid[0]) ** 2 +
            (centroid[1]) ** 2
        )
    

    def set_visibility(self, prim, visible):
        """
        주어진 프림의 가시성을 설정
        :param prim: 프림 객체
        :param visible: True면 가시, False면 비가시
        """
        visibility_attr = UsdGeom.Imageable(prim).GetVisibilityAttr()
        visibility_attr.Set("inherited" if visible else "invisible")

    def update_visibility_based_on_data(self, detection_results):
        """
        데이터에 따라 프림의 가시성을 업데이트
        :param detection_results: 데이터
        """
        # 데이터가 없으면 모든 프림을 비가시화
        if not detection_results:
            for prim in self.human_prim_list:
                self.set_visibility(prim, False)
        else:
            # 데이터가 있을 경우, 특정 프림을 가시화
            for index, detection in enumerate(detection_results):
                if index < len(self.human_prim_list):
                    self.set_visibility(self.human_prim_list[index], True)
                # 데이터 수보다 많은 프림이 있을 경우, 나머지를 비가시화
                for i in range(len(detection_results), len(self.human_prim_list)):
                    self.set_visibility(self.human_prim_list[i], False)