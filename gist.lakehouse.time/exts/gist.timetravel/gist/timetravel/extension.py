import omni.ext
import omni.client
import asyncio
import os
import time
import json
from aiokafka import AIOKafkaProducer
from datetime import datetime

class FolderMonitorExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        print("[folder_monitor_extension] Startup")

        # Configuration Variables
        self.omniverse_watch_path = "omniverse://10.32.133.81/Projects/demonstration/"
        self.kafka_bootstrap_servers = '210.125.85.62:9094'
        self.kafka_topic = 'omniverse-update'
        self.polling_interval_minutes = 1  # Polling interval in minutes

        # Allowed file extensions
        self.allowed_extensions = ['.usd', '.usdc', '.usda', '.usdz']

        # Path to store file modification times
        self.mod_times_file = 'C:/Users/nuc/file_mod_times.json'

        # Load previous modification times
        self.file_mod_times = self.load_mod_times()

        # Start the asynchronous monitoring task
        self.loop = asyncio.get_event_loop()
        self.monitor_task = self.loop.create_task(self.monitor_folder())

    def on_shutdown(self):
        print("[folder_monitor_extension] Shutdown")

        # Cancel the monitoring task
        if hasattr(self, 'monitor_task'):
            self.monitor_task.cancel()

    def load_mod_times(self):
        """
        Load the file modification times from the JSON file.
        """
        if os.path.exists(self.mod_times_file):
            try:
                with open(self.mod_times_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[folder_monitor_extension] Error loading mod times: {e}")
                return {}
        else:
            return {}

    def save_mod_times(self):
        """
        Save the file modification times to the JSON file.
        """
        try:
            with open(self.mod_times_file, 'w') as f:
                json.dump(self.file_mod_times, f)
        except Exception as e:
            print(f"[folder_monitor_extension] Error saving mod times: {e}")

    def create_entry_message(self, entry, file_url, relative_path):
            """
            Create a JSON-serializable message from a file entry.
            """
            def convert(value):
                if isinstance(value, datetime):
                    return value.isoformat()
                return value

            message = {
                'relative_path': relative_path,
                'access': getattr(entry, 'access', 0) or 0,
                'flags': getattr(entry, 'flags', 0) or 0,
                'size': getattr(entry, 'size', 0) or 0,
                'modified_time': convert(getattr(entry, 'modified_time', '')) or '',
                'modified_by': convert(getattr(entry, 'modified_by', '')) or '',
                'created_time': convert(getattr(entry, 'created_time', '')) or '',
                'created_by': convert(getattr(entry, 'created_by', '')) or '',
                'version': getattr(entry, 'version', '') or '',
                'hash': getattr(entry, 'hash', '') or '',
                'file_url': file_url,
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            }

            return message

    async def monitor_folder(self):
        """
        Monitor the specified Omniverse folder and send updates to Kafka.
        """
        # Initialize Kafka Producer
        producer = AIOKafkaProducer(bootstrap_servers=self.kafka_bootstrap_servers)
        await producer.start()
        print("[folder_monitor_extension] Kafka Producer started")

        try:
            while True:
                print(f"[{time.strftime('%Y%m%d_%H%M%S')}] Starting polling cycle")
                # Fetch all USD files recursively
                usd_entries = await self.get_all_usd_files(self.omniverse_watch_path)
                for file_info in usd_entries:
                    try:
                        entry = file_info['entry']
                        relative_path = file_info['full_relative_path']
                        # Construct file URL
                        file_url = f"{self.omniverse_watch_path}{relative_path}"

                        # Create message
                        message = self.create_entry_message(entry, file_url, relative_path)

                        # 필요한 경우 파일 내용을 읽어서 메시지에 포함
                        include_file = False  # 파일 내용을 포함하려면 True로 설정
                        if include_file:
                            file_content = await self.read_file_content(file_url)
                            if file_content is not None:
                                message['file_content'] = file_content

                        # Send message to Kafka asynchronously
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        try:
                            # Serialize message to JSON
                            message_json = json.dumps(message).encode('utf-8')
                            await producer.send_and_wait(self.kafka_topic, message_json)
                            print(f"[{timestamp}] Sent message to Kafka: {message}")
                        except Exception as e:
                            print(f"[folder_monitor_extension] Error sending to Kafka: {e}")

                    except Exception as e:
                        print(f"[folder_monitor_extension] Error processing entry: {e}")

                # Wait for the specified polling interval
                print(f"[{time.strftime('%Y%m%d_%H%M%S')}] Polling cycle completed. Waiting for {self.polling_interval_minutes} minutes.")
                await asyncio.sleep(self.polling_interval_minutes * 60)

        except asyncio.CancelledError:
            print("[folder_monitor_extension] Monitoring task cancelled")
        except Exception as e:
            print(f"[folder_monitor_extension] Error in monitoring: {e}")
        finally:
            await producer.stop()
            print("[folder_monitor_extension] Kafka Producer stopped")

    async def read_file_content(self, file_url):
        """
        Read file content asynchronously.
        """
        try:
            result, file_content = await omni.client.read_file_async(file_url)
            if result == omni.client.Result.OK:
                return file_content.decode('utf-8', errors='ignore')
            else:
                print(f"[folder_monitor_extension] Failed to read file: {file_url} - {result}")
                return None
        except Exception as e:
            print(f"[folder_monitor_extension] Error reading file content: {e}")
            return None

    async def get_all_usd_files(self, path):
        """
        Recursively fetch all USD and USDZ file entries within the specified Omniverse path.
        """
        usd_files = []
        stack = [(path, '')]

        while stack:
            current_path, current_relative_path = stack.pop()
            result, entries = await omni.client.list_async(current_path)
            if result != omni.client.Result.OK:
                print(f"[folder_monitor_extension] Failed to list folder: {current_path} - {result}")
                continue

            for entry in entries:
                try:
                    name = getattr(entry, 'relative_path', '')
                    if not name:
                        continue

                    # Remove trailing slashes
                    name = name.rstrip('/')

                    # Skip hidden files and folders
                    if name.lower().startswith('.'):
                        continue

                    # Build full relative path
                    full_relative_path = os.path.join(current_relative_path, name).replace('\\', '/')

                    # If the entry has an allowed extension, it's a file
                    if any(name.lower().endswith(ext) for ext in self.allowed_extensions):
                        # Append entry and full relative path
                        usd_files.append({'entry': entry, 'full_relative_path': full_relative_path})
                    else:
                        # Determine if the entry is a folder by checking if it has no file extension
                        _, ext = os.path.splitext(name)
                        if not ext:
                            # Ensure proper path formatting
                            if not current_path.endswith('/'):
                                current_path += '/'
                            subfolder_path = f"{current_path}{name}/"
                            stack.append((subfolder_path, full_relative_path))
                        else:
                            # It's a file with an unsupported extension; skip it
                            continue

                except Exception as e:
                    print(f"[folder_monitor_extension] Error processing entry: {e}")

        return usd_files
