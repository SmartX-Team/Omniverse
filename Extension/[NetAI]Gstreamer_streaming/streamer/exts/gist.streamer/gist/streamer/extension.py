import omni.ext
import omni.client
import asyncio
import os
import json
from datetime import datetime
import time
import redis.asyncio as redis

OMNIVERSE_PATH = "omniverse://10.32.133.81/Projects/demonstration/"
ALLOWED_EXTENSIONS = ['.usd', '.usdc', '.usda', '.usdz']
REDIS_HOST = "10.80.0.20"
REDIS_PORT = 6379
REDIS_DB = 0

async def list_usd_files(path):
    usd_files = []
    stack = [(path, '')]

    while stack:
        current_path, current_relative_path = stack.pop()
        result, entries = await omni.client.list_async(current_path)
        if result != omni.client.Result.OK:
            print(f"Failed to list folder: {current_path} - {result}")
            continue

        for entry in entries:
            try:
                name = getattr(entry, 'relative_path', '')
                if not name:
                    continue
                name = name.rstrip('/')
                if name.lower().startswith('.'):
                    continue

                full_relative_path = os.path.join(current_relative_path, name).replace('\\', '/')
                
                _, ext = os.path.splitext(name)
                if ext.lower() in ALLOWED_EXTENSIONS:
                    usd_files.append({'entry': entry, 'full_relative_path': full_relative_path})
                else:
                    if not ext:
                        # 폴더이면 재귀 탐색
                        if not current_path.endswith('/'):
                            current_path += '/'
                        subfolder_path = f"{current_path}{name}/"
                        stack.append((subfolder_path, full_relative_path))
                    else:
                        continue
            except Exception as e:
                print(f"Error processing entry in {current_path}: {e}")

    return usd_files

def convert_datetime(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)

async def main_task():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    print("Scanning Omniverse directory for USD files...")
    usd_entries = await list_usd_files(OMNIVERSE_PATH)

    print(f"Found {len(usd_entries)} USD entries. Caching to Redis...")
    pipeline = r.pipeline(transaction=False)
    for file_info in usd_entries:
        entry = file_info['entry']
        relative_path = file_info['full_relative_path']
        modified_time = convert_datetime(getattr(entry, 'modified_time', ''))
        data = {
            "modified_time": modified_time,
            "relative_path": relative_path
        }
        key = f"usd:{relative_path}"
        pipeline.set(key, json.dumps(data))

    await pipeline.execute()
    print("Caching completed.")

class FolderMonitorExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        print("[FolderMonitorExtension] Startup")
        
        # asyncio 이벤트 루프 얻기
        loop = asyncio.get_event_loop()
        
        # main_task를 태스크로 실행
        self._task = loop.create_task(main_task())

    def on_shutdown(self):
        print("[FolderMonitorExtension] Shutdown")
        if hasattr(self, '_task'):
            self._task.cancel()
            # 태스크가 완료되거나 취소될 때까지 여기서 기다릴 수도 있음
            # 필요하다면 try/except로 asyncio.CancelledError 처리 가능.
