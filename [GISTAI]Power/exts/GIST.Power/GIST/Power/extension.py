import omni.ext
import omni.ui as ui
import omni.usd
from pxr import Gf, Usd, UsdGeom, UsdShade
import requests
import json

class GistPowerExtension(omni.ext.IExt):
    def __init__(self):
        super().__init__()
        self.stage = omni.usd.get_context().get_stage()
        self.colors = {
            "Red": (1.0, 0.0, 0.0),
            "Yellow": (1.0, 1.0, 0.0),
            "Green": (0.0, 1.0, 0.0)
        }
        self.color_path = {
            "Red": "/World/Looks/poweroff",
            "Yellow": "/World/Looks/logout",
            "Green": "/World/Looks/poweron"
        }
        self.url = "http://10.32.187.108:5001/nodes"

    def on_startup(self, ext_id):
        print("[GIST.Power] GIST Power startup")

        self._window = ui.Window("Power Window", width=600, height=300)
        with self._window.frame:
            with ui.VStack():
                self.create_ui()

    def on_shutdown(self):
        print("[GIST.Power] GIST Power shutdown")

    def create_ui(self):
        def on_click():
            try:
                response = requests.get(self.url)
                response.raise_for_status()
                data = response.json()

                nuc_power_map = {item.get("Name", ""): [item.get("Status", ""), item.get("Login", "")] for item in data}

                for prim in self.stage.Traverse():
                    prim_name = prim.GetName()
                    if "Sphere" in prim_name or "Light" in prim_name:
                        xform = UsdGeom.Xform(prim)
                        key_name = self.get_nuc_name(str(xform.GetPath()))
                        if key_name:
                            color = get_power_color(nuc_power_map.get(key_name))
                            if color:
                                if "Light" in prim_name:
                                    attr = prim.GetAttribute("color")
                                    attr.Set(Gf.Vec3d(self.colors[color]))
                                elif "Sphere" in prim_name:
                                    material = UsdShade.Material.Get(self.stage, self.color_path[color])
                                    material_binding_api = UsdShade.MaterialBindingAPI.Apply(prim)
                                    material_binding_api.Bind(material)
            except requests.RequestException as e:
                print(f"Error fetching data: {e}")
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")

        with ui.HStack():
            ui.Button("Sync", clicked_fn=on_click)

    def get_nuc_name(self, path):
        parts = path.split("/")
        for part in parts:
            if "NUC" in part:
                return part
        return None

def get_power_color(nuc_power_info):
    if nuc_power_info:
        status, login = nuc_power_info
        if status == "NotReady":
            return "Red"
        elif status == "Ready" and login == "false":
            return "Yellow"
        elif status == "Ready" and login == "true":
            return "Green"
    return None
