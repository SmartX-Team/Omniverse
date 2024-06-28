from fastapi import FastAPI
from core.Websocket_raw import SewioWebSocketClient_v2
from core.data_process import DataHandleCallback

url = "ws://www.sewio-uwb.svc.ops.openark/sensmapserver/api"  # 실제 서버 URL로 교체 필요
client = SewioWebSocketClient_v2(url, data_callback=DataHandleCallback())
client.run_forever()


app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Hello, World!"}