import omni.ext
import omni.ui as ui
from omni.usd import get_context
from pxr import Usd, UsdGeom, UsdPhysics, UsdShade, Sdf, Gf, Tf, PhysxSchema
import asyncio
import json

try:
    import redis
except:
    omni.kit.pipapi.install("redis")
try:
    import httpx
except:
    omni.kit.pipapi.install("httpx")



#print(dir(UsdPhysics.CollisionAPI))

prim_map = {}
stage = get_context().get_stage()
# stage에서 모든 prim들을 순회하며 hashmap에 저장
for prim in stage.Traverse():
    prim_map[prim.GetName()] = prim

r = redis.StrictRedis(host='10.32.187.108', port=6379, db=0)
# Functions and vars are available to other extension as usual in python: `example.python_ext.some_public_function(x)`
def some_public_function(x: int):
    print("[GIST.UWB.traking] some_public_function was called with x: ", x)
    return x ** x

class CompanyHelloWorldExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.
    def __init__(self):
        # _count 변수 초기화
        self._count = 0
        self._test = 0
    def on_startup(self, ext_id):
        print("[GIST.UWB.traking] startup")


        self._window = ui.Window("UWB traking", width=500, height=300)
        with self._window.frame:
            with ui.VStack():
                label = ui.Label("")

                async def on_click_coroutine(label, _test, _count):  
                    self._count = 100

                    while self._count > 0 :
                        await move_objectoredis()
                        self._test += 1
                        label.text = f"count: {self._test}"
                        await asyncio.sleep(1)   

                def on_reset():
                    
                    self._test = 0
                    label.text = f"count: {self._test}"
                    self._count = 0
                    #try :
                    #except Exception as e:
                        #label.text = f"Error: {e}"

                with ui.HStack():
                    ui.Button("UWB on", clicked_fn=lambda: asyncio.ensure_future(on_click_coroutine(label, self._test, self._count)))
                    ui.Button("UWB off", clicked_fn=on_reset)
                    ui.Button("WebView", clicked_fn=lambda: asyncio.ensure_future(sage2()))

    def on_shutdown(self):
        print("[company.hello.world] company hello world shutdown")

     
async def move_objectoredis():

    data = r.rpop('uwb_queue')
    while data:  # data가 None이 아닐 때까지 반복
    # 여기서 data를 처리합니다. 예를 들면:
        deserialized_data = json.loads(data.decode('utf-8'))
        x, z = await transform_coordinates(deserialized_data['posX'], deserialized_data['posY'])
        obj_name = deserialized_data['alias'].replace('/', '_')
        translation = [z, 90.0, x]  # Move 10 units in X and 5 units in Z
        print(translation)
        await move_object_by_name(obj_name, translation)

        data = r.rpop('uwb_queue')

async def transform_coordinates(x, y):
  
    m_x = (x) *100
    m_y = -(y) *100
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
    """
    for prim in stage.Traverse():
        if prim.GetName() == obj_name:
            #xformable = UsdGeom.Xformable(prim)
            xformAPI = UsdGeom.XformCommonAPI(prim)
            api = UsdPhysics.CollisionAPI(prim)
            print(api)
            print(api.CreateCollisionEnabledAttr(True))
            print(api.GetCollisionEnabledAttr())

            # Apply translation
            xformAPI.SetTranslate(Gf.Vec3d(translation[0], translation[1], translation[2]))

            print(f"Moved object {obj_name} to new position.")
            return

    print(f"Object {obj_name} not found.")
    """
async def sage2():
    data = "open http://10.32.205.64:6080/vnc_lite.html?scale=true"

    # httpx를 사용하여 POST 요청 실행
    response = await httpx.post("http://10.32.187.108:9292/command", data=data)

