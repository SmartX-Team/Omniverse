import asyncio, math, random, time
import omni.kit.app
from omni.kit.viewport.utility import get_active_viewport
from omni.kit.viewport.utility.camera_state import ViewportCameraState
from pxr import Gf

MIN = 15.0

async def run():
    cam = ViewportCameraState(viewport=get_active_viewport())
    c = Gf.Vec3d(cam.target_world)
    d0 = (Gf.Vec3d(cam.position_world) - c).GetLength() or 100.0
    app = omni.kit.app.get_app()
    end = time.time() + MIN * 60
    p, g = Gf.Vec3d(cam.position_world), Gf.Vec3d(c)
    while time.time() < end:
        yaw = random.uniform(-math.pi, math.pi)
        pit = math.radians(random.uniform(10, 60))
        d = d0 * random.uniform(0.6, 1.6)
        np = c + Gf.Vec3d(d*math.cos(pit)*math.cos(yaw), d*math.cos(pit)*math.sin(yaw), d*math.sin(pit))
        ng = c + Gf.Vec3d(*(random.uniform(-1, 1)*0.15*d0 for _ in range(3)))
        lt, t0, sp, sg = random.uniform(2, 5), time.time(), Gf.Vec3d(p), Gf.Vec3d(g)
        while time.time() - t0 < lt and time.time() < end:
            f = (time.time() - t0) / lt
            e = f*f*(3-2*f)
            cam.set_position_world(Gf.Lerp(e, sp, np), True)
            cam.set_target_world(Gf.Lerp(e, sg, ng), True)
            await app.next_update_async()
        p, g = np, ng
    print("done")

try:
    T.cancel()
except NameError:
    pass
T = asyncio.ensure_future(run())
print("started")
