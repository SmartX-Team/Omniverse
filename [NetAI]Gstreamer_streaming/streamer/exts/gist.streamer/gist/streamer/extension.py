import omni.ext
import omni.ui as ui
import asyncio
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

Gst.init(None)

class StreamExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        print("[stream_screen] MyExtension startup")

        # Example of starting the stream
        asyncio.ensure_future(self.start_stream())

    def on_shutdown(self):
        print("[stream_screen] MyExtension shutdown")

    async def start_stream(self):
        pipeline = Gst.parse_launch(
            "nvarguscamerasrc ! videoconvert ! video/x-raw,width=1280,height=720,framerate=30/1 ! x264enc ! rtph264pay ! udpsink host=<TARGET_IP> port=<PORT>"
        )
        pipeline.set_state(Gst.State.PLAYING)

        # Run the GStreamer main loop
        loop = asyncio.get_running_loop()
        loop.add_reader(pipeline.get_bus().get_fd(), self._on_bus_message, pipeline.get_bus())

    def _on_bus_message(self, bus):
        message = bus.pop()
        if message:
            if message.type == Gst.MessageType.EOS:
                print('End of stream')
                bus.pipeline.set_state(Gst.State.NULL)
            elif message.type == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                print(f"Error: {err}, {debug}")
                bus.pipeline.set_state(Gst.State.NULL)

