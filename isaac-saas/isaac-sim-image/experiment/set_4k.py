import carb.settings
from omni.kit.viewport.utility import get_active_viewport

W, H, BITRATE = 3840, 2160, 104857600

s = carb.settings.get_settings()
s.set("/app/renderer/resolution/width", W)
s.set("/app/renderer/resolution/height", H)
s.set("/app/omni.videoencoding/bitrate", BITRATE)

vp = get_active_viewport()
vp.resolution = (W, H)

out = "renderer=%sx%s bitrate=%s viewport=%s" % (
    s.get("/app/renderer/resolution/width"),
    s.get("/app/renderer/resolution/height"),
    s.get("/app/omni.videoencoding/bitrate"),
    str(tuple(vp.resolution)),
)
open("/tmp/chk.txt", "w").write(out + "\n")
print(out)
