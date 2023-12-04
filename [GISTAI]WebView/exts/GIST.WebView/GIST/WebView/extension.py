import omni.ext
import omni.ui as ui
import requests

try:
    import requests
except:
    omni.kit.pipapi.install("requests")


class GistWebviewExtension(omni.ext.IExt):
    nuc_power_map = {}  # A dictionary that maps NUC name to its power status
    def update_nuc_status(self):
        response = requests.get("http://10.32.74.71:5000/nodes")
        if response.status_code == 200:
            data = response.json()

            

            for item in data:
                name = self.get_nuc_name(item.get("Name", ""))
                status = item.get("Status", "")
                login = item.get("Login", "")
                address = item.get("Address", "")
                self.nuc_power_map[name] = [status, login, address]

            # Update the labels based on the nuc_power_map
            for key, value in self.nuc_power_map.items():
                if value[0] == "NotReady":
                    self.labels[key].text = f"{key} : poweroff"
                    self.update_buttons[key].visible = False
                elif value[0] == "Ready":
                    self.update_buttons[key].visible = True
                    if value[1] == "false":
                        self.labels[key].text = f"{key} : poweron, logout"
                    elif value[1] == "true":
                        self.labels[key].text = f"{key} : poweron, login"

    def get_nuc_name(self, path):
        # Split the path by "/"
        path = str(path)
        parts = path.split("/")
        
        # Find the part that contains "NUC"
        for part in parts:
            if "NUC" in part:
                return part
        
        return None  # Return None if no part contains "NUC"

    def on_startup(self, ext_id):
        print("[GIST.WebView] GIST WebView startup")

        # 데이터 초기화
        self.data = {f"NUC11_{str(i).zfill(2)}": 0 for i in range(1, 11)}
        self.data.update({f"NUC12_{str(i).zfill(2)}": 0 for i in range(1, 21)})

        self._window = ui.Window("webview", width=400, height=800)
        with self._window.frame:
            with ui.VStack() as main_stack:
                # Update All labels and WebView buttons
                ui.Button("Update All", clicked_fn=self.update_nuc_status)

                # Assuming you already have a dictionary of labels and update buttons:
                self.labels = {}
                self.update_buttons = {}
                for key in self.data.keys():
                    with ui.HStack():
                        self.labels[key] = ui.Label(f"{key}: ", parent=main_stack)
                        self.update_buttons[key] = ui.Button("webview", clicked_fn=lambda k=key: self.sage2_webview(k), parent=main_stack)


        self.update_nuc_status()

    def sage2_webview(self, key):
        # key에 맞는 IP 주소를 nuc_power_map에서 찾습니다.
        nuc_info = self.nuc_power_map.get(key)
        if not nuc_info:
            print(f"Error: NUC info not found for {key}")
            return

        ip_address = nuc_info[2]  # Address is the third item in the list
        if not ip_address:
            print(f"Error: IP address not found for {key}")
            return

        # IP 주소를 사용하여 URL을 생성합니다.
        data = f"open http://{ip_address}:6080/vnc_lite.html?scale=true"

        # httpx를 사용하여 POST 요청 실행
        response = requests.post("http://10.32.187.108:9292/command", data=data)


    def on_shutdown(self):
        print("[GIST.WebView] GIST WebView shutdown")
