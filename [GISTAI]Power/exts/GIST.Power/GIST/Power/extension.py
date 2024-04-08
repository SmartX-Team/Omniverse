import omni.ext
import omni.ui as ui
import omni.usd
from pxr import Gf, Usd, UsdGeom, UsdShade
import requests
import json

try:
    import requests
except:
    omni.kit.pipapi.install("requests")

# Any class derived from `omni.ext.IExt` in top level module (defined in `python.modules` of `extension.toml`) will be
# instantiated when extension gets enabled and `on_startup(ext_id)` will be called. Later when extension gets disabled
# on_shutdown() is called.
class GistPowerExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.

    stage = omni.usd.get_context().get_stage()
    colors = {
    "Red": (1.0, 0.0, 0.0),
    "Yellow": (1.0, 1.0, 0.0),
    "Green": (0.0, 1.0, 0.0)
    }
    color_path = {
    "Red": "/World/Looks/poweroff",
    "Yellow": "/World/Looks/logout",
    "Green": "/World/Looks/poweron"
    }


    for prim in stage.Traverse():
        prim_name = prim.GetName()
        if "Sphere" in prim_name or "light" in prim_name:
            print(prim_name)
            xform = UsdGeom.Xform(prim)
            print(xform.GetPath())


    def on_startup(self, ext_id):
        print("[GIST.Power] GIST Power startup")
        stage = omni.usd.get_context().get_stage()

        self._count = 0

        self._window = ui.Window("Power Window", width=600, height=300)
        with self._window.frame:
            with ui.VStack():
                label = ui.Label("")

                def on_click():
                    response = requests.get("http://10.32.74.69:5000/nodes")

                    if response.status_code == 200:
                        data = response.json()

                        nuc_power_map = {}  # Dictionary to store NUC_name as key and power as value

                        for item in data:
                            name = item.get("Name", "")  # Assuming the attribute's name is "path"
                            status = item.get("Status", "")  # Assuming there's an attribute named "power" for power status
                            login = item.get("Login", "")  # Assuming there's an attribute named "power" for power status
                           
                            nuc_power_map[name] = [status, login]

                        
                        print(nuc_power_map)
                        for prim in stage.Traverse():
                            prim_name = prim.GetName()
                            if "Sphere" in prim_name or "Light" in prim_name:
                                xform = UsdGeom.Xform(prim)
                                key_name = self.get_nuc_name(xform.GetPath())
                                if key_name is not None:
                                    color = get_power_color(nuc_power_map[key_name])

                                    if "Light" in prim_name:
                                        attr = prim.GetAttribute("color")
                                        attr.Set(Gf.Vec3d(self.colors[color]))

                                         
                                    elif "Sphere" in prim_name:
                                        material = UsdShade.Material.Get(stage, self.color_path[color])
                                        material_binding_api = UsdShade.MaterialBindingAPI.Apply(prim)
                                        material_binding_api.Bind(material)


                    #prim = stage.GetPrimAtPath("/World/NUC12_07/Geometry/cart_12/Sphere/SphereLight")


                def on_reset():
                    self._count = 0
                    label.text = "empty"

                on_reset()

                with ui.HStack():
                    ui.Button("start", clicked_fn=on_click)
                    ui.Button("stop", clicked_fn=on_reset)

    def on_shutdown(self):
        print("[GIST.Power] GIST Power shutdown")

    #"This function extracts the NUC PC information from the path and returns it."
    def get_nuc_name(self, path):
        # Split the path by "/"
        path = str(path)
        parts = path.split("/")
        
        # Find the part that contains "NUC"
        for part in parts:
            if "NUC" in part:
                return part
        
        return None  # Return None if no part contains "NUC"


# It provides the appropriate power color based on the NUC information.
def get_power_color(nuc_power_info):

    if nuc_power_info is not None:
        status = nuc_power_info[0] 
        login = nuc_power_info[1]

        # Check the status and login values and return the appropriate color
        if status == "NotReady":
            return "Red"
        elif status == "Ready" and login == "false":
            return "Yellow"
        elif status == "Ready" and login == "true":
            return "Green"
    
    return None  # Return None if the NUC_name doesn't exist in the map 