"""
Author: Inyong Song
Documentation Date: 12/04/24

This code generates image data from the webcam of virtual MobileX Stations in Omniverse and transmits it through Kafka, which is then stored and managed in the Lakehouse.

Currently, the code was tested with only one MobileX station, but the goal is to eventually generate and manage image data from all virtual MobileX Stations in the completed version.

When the Extension is first executed, it creates a Camera View if one doesn't exist; if a warning error occurs during this process, simply re-run the Extension.

"""

import omni
import asyncio
from pxr import Usd, UsdGeom, Gf
from aiokafka import AIOKafkaProducer
import numpy as np
import io
from PIL import Image
import ctypes

# MobileX Station path settings
MOBILEX_STATION_PATH = '/World/station/NUC11_01'
WEBCAM_PRIM_NAME = 'Geometry/cart/webcam/Logitech_Webcam'
CAMERA_PRIM_NAME = 'CameraView'

# Kafka settings
KAFKA_BOOTSTRAP_SERVERS = '210.125.85.62:9094'
KAFKA_TOPIC = 'wow20-camera'
MAX_REQUEST_SIZE = 20971520  # 20 MB

async def capture_and_send_image(viewport_api, producer):
    from omni.kit.widget.viewport.capture import ByteCapture

    try:
        # Wait for viewport to update
        await omni.kit.app.get_app().next_update_async()

        # Define a future to hold the capture result
        future = asyncio.get_event_loop().create_future()

        def on_capture_completed(buffer_ptr, buffer_size, width, height, format):
            try:
                # Access the buffer data using ctypes
                PyCapsule_GetPointer = ctypes.pythonapi.PyCapsule_GetPointer
                PyCapsule_GetPointer.restype = ctypes.c_void_p
                PyCapsule_GetPointer.argtypes = [ctypes.py_object, ctypes.c_char_p]

                buffer_address = PyCapsule_GetPointer(buffer_ptr, None)
                if not buffer_address:
                    raise ValueError("Cannot get buffer address from PyCapsule")

                # Create a ctypes array from the buffer
                buffer_type = ctypes.c_uint8 * buffer_size
                buffer = buffer_type.from_address(buffer_address)

                # Convert the buffer to a bytes object
                buffer_bytes = bytes(buffer)

                # Prepare the result without including 'format'
                future.set_result({
                    'buffer_bytes': buffer_bytes,
                    'width': width,
                    'height': height,
                })
            except Exception as e:
                future.set_exception(e)

        # Create a ByteCapture delegate
        capture_delegate = ByteCapture(on_capture_completed)

        # Schedule the capture
        capture = viewport_api.schedule_capture(capture_delegate)

        # Wait for the capture to complete
        await capture.wait_for_result()

        # Wait for the on_capture_completed callback
        result = await future

        buffer_bytes = result['buffer_bytes']
        width = result['width']
        height = result['height']

        # Convert buffer_bytes to NumPy array
        img_array = np.frombuffer(buffer_bytes, dtype=np.uint8)
        img_array = img_array.reshape((height, width, 4))  # Assuming RGBA format

        # Convert to PIL Image
        image = Image.fromarray(img_array, 'RGBA')

        # Save image to bytes buffer in PNG format
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG')
        png_image_bytes = img_buffer.getvalue()

        # Send PNG image bytes over Kafka
        await producer.send_and_wait(KAFKA_TOPIC, png_image_bytes)
        print(f"PNG image sent to Kafka topic '{KAFKA_TOPIC}'")
    except Exception as e:
        print(f"Error capturing or sending image: {e}")


async def main():
    # Get the USD Stage
    stage = omni.usd.get_context().get_stage()

    # Check MobileX Station Prim
    mobilex_station_prim = stage.GetPrimAtPath(MOBILEX_STATION_PATH)
    if not mobilex_station_prim.IsValid():
        print(f"MobileX Station Prim does not exist at the path: {MOBILEX_STATION_PATH}")
        return
    else:
        # Check 'Webcam' Prim
        webcam_prim_path = f"{MOBILEX_STATION_PATH}/{WEBCAM_PRIM_NAME}"
        webcam_prim = stage.GetPrimAtPath(webcam_prim_path)
        if not webcam_prim.IsValid():
            print(f"'Webcam' Prim does not exist under MobileX Station: {webcam_prim_path}")
            return
        else:
            # Check Camera Prim
            camera_prim_path = f"{webcam_prim_path}/{CAMERA_PRIM_NAME}"
            camera_prim = stage.GetPrimAtPath(camera_prim_path)
            if not camera_prim.IsValid():
                # Create Camera Prim
                camera_prim = UsdGeom.Camera.Define(stage, camera_prim_path)
                print(f"Created Camera Prim: {camera_prim_path}")

                # Set Camera Transform (same as 'Webcam')
                webcam_xform = UsdGeom.Xformable(webcam_prim)
                camera_xform = UsdGeom.Xformable(camera_prim)

                # Get 'Webcam' local transformation matrix
                webcam_transform = webcam_xform.ComputeLocalToWorldTransform()
                # Apply transformation matrix to camera
                camera_xform.ClearXformOpOrder()
                camera_xform.AddTransformOp().Set(webcam_transform)
            else:
                print(f"Camera Prim already exists: {camera_prim_path}")

            # Switch viewport to camera
            from omni.kit.viewport.utility import get_active_viewport

            # Get active viewport
            viewport_api = get_active_viewport()
            if viewport_api:
                # Set the viewport camera to the newly created camera
                viewport_api.camera_path = camera_prim_path
                print(f"Viewport camera set to: {viewport_api.camera_path}")

                # Wait for the viewport to update
                await omni.kit.app.get_app().next_update_async()
                await omni.kit.app.get_app().next_update_async()
                print("Viewport has been updated.")

                # Initialize Kafka producer with increased max_request_size
                producer = AIOKafkaProducer(
                    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                    max_request_size=MAX_REQUEST_SIZE,
                    compression_type='gzip'  # Enable compression
                )
                await producer.start()
                print("Kafka producer started.")

                try:
                    # Capture and send images periodically
                    while True:
                        await capture_and_send_image(viewport_api, producer)
                        # Wait for the desired interval (e.g., 5 seconds)
                        await asyncio.sleep(5)
                except KeyboardInterrupt:
                    print("Stopping image capture.")
                finally:
                    await producer.stop()
                    print("Kafka producer stopped.")
            else:
                print("Cannot get viewport API instance.")

# Schedule the main function to run asynchronously
asyncio.ensure_future(main())
