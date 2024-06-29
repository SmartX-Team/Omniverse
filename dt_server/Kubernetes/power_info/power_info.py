from flask import Flask, jsonify
from kubernetes import client, config

app = Flask(__name__)

try:
    with open("/root/.kube/config", "r") as f:
        print(f.read())
except Exception as e:
    print(f"Error reading Kubernetes config file: {e}")

config.load_kube_config(config_file="/root/.kube/config")

MAP_DATA = {
    "cafd5a3e-19ba-3a14-df21-1c697ad50493":"NUC11_01",
    "18e1df49-96e8-8e0b-edb6-1c697ad506b6":"NUC11_02",
    "13011dc2-7ced-e6c1-150b-1c697ad507a6":"NUC11_03",
    "efdb1771-5f9f-a027-d863-1c697ad5013e":"NUC11_04",
    "653fbdde-3267-14f1-360e-1c697ad502d0":"NUC11_05",
    "0adbb676-cb42-0882-ce12-1c697ad506cb":"NUC11_06",
    "37dd943b-4abb-a777-224b-1c697ad50558":"NUC11_07",
    "784a8a47-0153-1f8a-ffd3-1c697ad50485":"NUC11_08",
    "90a0fd91-ade8-69bc-f4a1-1c697ad5079b":"NUC11_09",
    "b80cc5d8-e1be-f6b8-a03e-1c697ad5015f":"NUC11_10",
    "fc1258ba-b25c-2724-d6d7-1c697ad99de0":"NUC12_01",
    "fe47eb1b-cf4c-f3fb-5057-1c697ad99f56":"NUC12_02",
    "02ca34fa-a216-9a2b-2a0a-1c697ad8c177":"NUC12_03",
    "9bc3697d-072e-dc48-29fb-1c697ad99e51":"NUC12_04",
    "9bcc45d1-c926-ab80-b3c0-1c697ad99d94":"NUC12_05",
    "92404821-7051-5c93-90bd-1c697ad8c045":"NUC12_06",
    "9f351faf-d85c-e39e-1e64-1c697ad8c10d":"NUC12_07",
    "5c85978f-e920-9ebf-9334-1c697ad8c107":"NUC12_08",
    "da454806-2e36-f088-f10e-1c697ad8c03f":"NUC12_09",
    "3adacb41-faad-9484-7477-1c697ad8c17d":"NUC12_10",
    "99effe4d-6ea9-56a4-c5c8-1c697ad99dc1":"NUC12_11",
    "a9fa482b-1e0a-e75e-2236-1c697ad99f5f":"NUC12_12",
    "11b95e87-0f9f-391b-2357-1c697ad8bfea":"NUC12_13",
    "ffb521e3-8dea-0d79-65fb-1c697ad8c124":"NUC12_14",
    "e4020aba-4b62-55fa-1362-1c697ad99df2":"NUC12_15",
    "cb47d8b7-008b-d945-c9e1-1c697ad8c0b9":"NUC12_16",
    "1e35b5a9-ca19-33f3-94b3-1c697ad99f0c":"NUC12_17",
    "5f0e2f32-c2f8-e3a8-a6f9-1c697ad8c015":"NUC12_18",
    "895927f7-5f36-b840-731e-1c697ad99eb0":"NUC12_19",
    "c2136df7-8483-22eb-3210-1c697ad99e00":"NUC12_20"
}
v1 = client.CoreV1Api()

# kubectl get nodes 와 fetch_boxes_info 를 이용하여 현재 NUC_PC들의 정보를 가져와 REST API로 제공합니다.
@app.route('/nodes', methods=['GET'])
def get_nodes():
    ret = v1.list_node(pretty=True)
    address_info = fetch_boxes_info()

    nodes = []
    for node in ret.items:
        if node.metadata.name in MAP_DATA:
            for condition in node.status.conditions:
                if condition.type == "Ready":
                    status = condition.status
                    break

            label_value = node.metadata.labels.get("ark.ulagbulag.io/bind", None)
            nuc_name = MAP_DATA[node.metadata.name]
            address = address_info.get(nuc_name, "N/A")
            
            if status == 'True' and label_value:
                nodes.append({
                    "Id": node.metadata.name,
                    "Name": nuc_name,
                    "Address": address,
                    "Status": "Ready",
                    "Login": label_value
                })
            elif status != 'True':
                nodes.append({
                    "Id": node.metadata.name,
                    "Name": nuc_name,
                    "Address": address,
                    "Status": "NotReady",
                    "Login": "false"
                })
    
    return jsonify(nodes)

#kubectl get boxes 로 얻는 정보 중에서 address 정보를 가져옵니다.
def fetch_boxes_info():
    config.load_kube_config('~/.kube/config')
    v1 = client.CustomObjectsApi()

    group = 'kiss.ulagbulag.io'  # API Group
    version = 'v1alpha1'  # Version
    plural = 'boxes'  # Plural name

    boxes = v1.list_cluster_custom_object(group, version, plural)
    address_map = {}  # name을 키로하고 address를 값으로 가지는 맵

    for box in boxes['items']:
        name_key = box['metadata']['name']
        if name_key in MAP_DATA:  # 매핑 정보에 존재하는 키인지 확인
            nuc_name = MAP_DATA[name_key]
            address = box['status']['access']['primary']['address']
            address_map[nuc_name] = address

    return address_map

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
