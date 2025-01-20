import omni.ext
import omni.ui as ui
from omni.usd import get_context
from pxr import Usd, UsdGeom, Gf, Tf, PhysxSchema
import asyncio
import requests

try:
    import requests
except:
    omni.kit.pipapi.install("requests")

MAP_DATA =(
    "cafd5a3e-19ba-3a14-df21-1c697ad50493,24",
    "18e1df49-96e8-8e0b-edb6-1c697ad506b6,40",
    "13011dc2-7ced-e6c1-150b-1c697ad507a6,39",
    "efdb1771-5f9f-a027-d863-1c697ad5013e,37",
    "653fbdde-3267-14f1-360e-1c697ad502d0,36",
    "0adbb676-cb42-0882-ce12-1c697ad506cb,31",
    "37dd943b-4abb-a777-224b-1c697ad50558,49",
    "784a8a47-0153-1f8a-ffd3-1c697ad50485,25",
    "90a0fd91-ade8-69bc-f4a1-1c697ad5079b,44",
    "b80cc5d8-e1be-f6b8-a03e-1c697ad5015f,23",
    "fc1258ba-b25c-2724-d6d7-1c697ad99de0,20",
    "fe47eb1b-cf4c-f3fb-5057-1c697ad99f56,22",
    "02ca34fa-a216-9a2b-2a0a-1c697ad8c177,46",
    "9bc3697d-072e-dc48-29fb-1c697ad99e51,19",
    "9bcc45d1-c926-ab80-b3c0-1c697ad99d94,45",
    "92404821-7051-5c93-90bd-1c697ad8c045,29",
    "9f351faf-d85c-e39e-1e64-1c697ad8c10d,18",
    "5c85978f-e920-9ebf-9334-1c697ad8c107,33",
    "da454806-2e36-f088-f10e-1c697ad8c03f,43",
    "3adacb41-faad-9484-7477-1c697ad8c17d,26",
    "99effe4d-6ea9-56a4-c5c8-1c697ad99dc1,48",
    "a9fa482b-1e0a-e75e-2236-1c697ad99f5f,41",
    "11b95e87-0f9f-391b-2357-1c697ad8bfea,21",
    "ffb521e3-8dea-0d79-65fb-1c697ad8c124,35",
    "e4020aba-4b62-55fa-1362-1c697ad99df2,47",
    "cb47d8b7-008b-d945-c9e1-1c697ad8c0b9,38",
    "1e35b5a9-ca19-33f3-94b3-1c697ad99f0c,9",
    "5f0e2f32-c2f8-e3a8-a6f9-1c697ad8c015,34",
    "895927f7-5f36-b840-731e-1c697ad99eb0,32",
    "c2136df7-8483-22eb-3210-1c697ad99e00,42"
)
# 하드 코딩 드가자
show_dict = {}
show_dict['NUC11_01'] = [[-90,0,0],[600,90,500]]
show_dict['NUC11_02'] = [[-90,0,0],[480,90,500]]
show_dict['NUC11_03'] = [[-90,0,0],[360,90,500]]
show_dict['NUC11_04'] = [[-90,0,0],[240,90,500]]
show_dict['NUC11_05'] = [[-90,0,0],[120,90,500]]
show_dict['NUC11_06'] = [[-90,0,0],[120,90,600]]
show_dict['NUC11_07'] = [[-90,0,0],[240,90,600]]
show_dict['NUC11_08'] = [[-90,0,0],[360,90,600]]
show_dict['NUC11_09'] = [[-90,0,0],[480,90,600]]
show_dict['NUC11_10'] = [[-90,0,0],[600,90,600]]

show_dict['NUC12_01'] = [[-90,90,0],[1920,90,1900]]
show_dict['NUC12_02'] = [[-90,0,0],[1980,90,800]]
show_dict['NUC12_03'] = [[-90,0,0],[2110,90,800]]
show_dict['NUC12_04'] = [[-90,0,0],[2250,90,800]]
show_dict['NUC12_05'] = [[-90,0,0],[2390,90,800]]
show_dict['NUC12_06'] = [[-90,0,0],[2520,90,940]]
show_dict['NUC12_07'] = [[-90,90,0],[1810,90,1910]]
show_dict['NUC12_08'] = [[-90,0,0],[1980,90,940]]
show_dict['NUC12_09'] = [[-90,0,0],[2120,90,940]]
show_dict['NUC12_10'] = [[-90,90,0],[1810,90,1725]]
show_dict['NUC12_11'] = [[-90,0,0],[2380,90,942]]
show_dict['NUC12_12'] = [[-90,0,0],[2240,90,942]]
show_dict['NUC12_13'] = [[-90,-90,0],[2245,90,1583]]
show_dict['NUC12_14'] = [[-90,90,0],[1810,90,1814]]
show_dict['NUC12_15'] = [[-90,-90,0],[2242,90,1674]]
show_dict['NUC12_16'] = [[-90,-90,0],[2244,90,1763]]
show_dict['NUC12_17'] = [[-90,-90,0],[2106,90,1830]]
show_dict['NUC12_18'] = [[-90,0,0],[2510,90,800]]
show_dict['NUC12_19'] = [[-90,-90,0],[2106,90,1713]]
show_dict['NUC12_20'] = [[-90,90,0],[1810,90,1636]]


prim_map = {}
stage = get_context().get_stage()
# stage에서 모든 prim들을 순회하며 hashmap에 저장
for prim in stage.Traverse():
    prim_map[prim.GetName()] = prim

print(prim_map['NUC11_01'])

# API endpoint 및 headers 정보
BASE_URL = "http://www.sewio-uwb.svc.ops.openark/sensmapserver/api/tags/{}"
headers = {
    'X-Apikey': '17254faec6a60f58458308763'
}

class CompanyHelloWorldExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.
    def __init__(self):
        print("[GIST Showing] startup")


    def on_startup(self, ext_id):
        
        self._window = ui.Window("Showing Window", width=600, height=300)
        with self._window.frame:
            with ui.VStack():

                async def on_click_uwbalign():  

                    await move_object_by_uwb()

                def on_click_showing():

                    move_object_by_show()

                with ui.HStack():
                    ui.Button("UWB align", clicked_fn=lambda: asyncio.ensure_future(on_click_uwbalign()))
                    ui.Button("show align", clicked_fn=on_click_showing)

    def on_shutdown(self):
        print("[company.hello.world] company hello world shutdown")

async def transform_coordinates(x, y):
  
    m_x = (x) *100
    m_y = -(y) *100
    x_prime = round(m_x, 2)
    z_prime = round(m_y, 2)

    return x_prime, z_prime

async def move_object_by_uwb():
    """
    Move an object by its name in Omniverse.

    Parameters:
    - obj_name (str): The name of the object.
    - translation (list): A list containing the x, y, and z translation values.
    """

    # 먼저 uwb MAP 에서 모든 id를 기준으로 REST API를 호출한다.
    id_to_alias = {}
    ids = [item.split(",")[1] for item in MAP_DATA]
    for id_ in ids:
        url = BASE_URL.format(id_)
        response = requests.get(url, headers=headers)
        response_data = response.json()
        key_name = response_data["alias"].replace('/', '_')

        temp_data_object = {
            "id": response_data["id"],
            "alias": key_name
        }
        if key_name in id_to_alias :
            continue
        else:
            for datastream in response_data['datastreams']:
                if datastream['id'] == 'posX':
                    temp_data_object["posX"] = float(datastream['current_value'].strip())
                elif datastream['id'] == 'posY':
                    temp_data_object["posY"] = float(datastream['current_value'].strip())
            id_to_alias[key_name] = temp_data_object

    stage = get_context().get_stage()
    # 이후에 추가된 객체라 primmap에 없는 객체는 Map에 추가한후 이동시킨다.
    keys_list = list(show_dict.keys())
    for id_ in keys_list:

        if id_ in prim_map:
            prim = prim_map[id_]
            xformAPI = UsdGeom.XformCommonAPI(prim)

            # Apply translation
            transform_coordinates_result = await transform_coordinates(id_to_alias[prim.GetName()]["posX"], id_to_alias[prim.GetName()]["posY"])
            xformAPI.SetTranslate(Gf.Vec3d(transform_coordinates_result[1], 90.0, transform_coordinates_result[0]))
        else:
            for prim in stage.Traverse():

                if id_ in id_to_alias:
                    xformAPI = UsdGeom.XformCommonAPI(prim)
                    # Apply translation
                    transform_coordinates_result = await transform_coordinates(id_to_alias[prim.GetName()]["posX"], id_to_alias[prim.GetName()]["posY"])
                    xformAPI.SetTranslate(Gf.Vec3d(transform_coordinates_result[1], 90.0, transform_coordinates_result[0]))
                    prim_map[id_] = prim
                else :
                    print('this name is not in stage')

def move_object_by_show():
    keys_list = list(show_dict.keys())
    for id_ in keys_list:
        if id_ in prim_map:
            prim = prim_map[id_]
            xformAPI = UsdGeom.XformCommonAPI(prim)
            xformAPI.SetTranslate(Gf.Vec3d(show_dict[id_][1][0], show_dict[id_][1][1], show_dict[id_][1][2]))
            rotation_value = Gf.Vec3f(show_dict[id_][0][0], show_dict[id_][0][1], show_dict[id_][0][2])
            xformAPI.SetRotate(rotation_value)
        else:
            print('this name is not in stage')