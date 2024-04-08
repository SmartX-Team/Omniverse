from omni.kit.scripting import BehaviorScript
import omni
import omni.physx
from pxr import Gf, Sdf, PhysxSchema, UsdGeom, Usd
from omni.physx.scripts import utils
from omni.physx import get_physx_scene_query_interface
from omni.physx import get_physx_interface, get_physx_simulation_interface
from omni.physx.scripts.physicsUtils import *
import carb

class CollisionTest(BehaviorScript):

    def on_init(self):
        self._contact_report_sub = None
        self.ignore_objects = []
        self.pallet_collection = 0
        self.collected_attr = self.prim.CreateAttribute('Collected', Sdf.ValueTypeNames.Int)
        self.collected_attr.Set(0)
        self.reset_character()
        print('Collision Test Initialized')

    def on_play(self):

        ''''
        Called on runtime
        '''
    
        self.reset_character()
        self._contact_report_sub = get_physx_simulation_interface().subscribe_contact_report_events(self._on_contact_report_event)
        contactReportAPI = PhysxSchema.PhysxContactReportAPI.Apply(self.prim)
        contactReportAPI.CreateThresholdAttr().Set(self.contact_thresh)

    def on_stop(self):
        self.on_destroy()


    def on_destroy(self):
        self.pallet = None
        self.collected_attr.Set(0)
        if hasattr(self, '_contact_report_sub') and self._contact_report_sub:
            self._contact_report_sub.unsubscribe()
            self._contact_report_sub = None

    def reset_character(self):
        self.contact_thresh = 1
        self.collected_attr.Set(0)
        self.pallet_collection = 0
        self.ignore_objects = []

        # Assign this pallet as agent instance
        self.pallet = str(self.prim_path)

        # parent_prim = self.stage.GetPrimAtPath(self.package_path)
        # if parent_prim.IsValid():
        #     children = parent_prim.GetAllChildren()
        #     self.package = [str(child.GetPath()) for child in children]


    def on_update(self, current_time: float, delta_time: float):
        """
        Called on every update. Initializes character at start, 
        publishes character positions and executes character commands.
        :param float current_time: current time in seconds.
        :param float delta_time: time elapsed since last update.
        """

        return 

    def subscribe_to_contact(self):
    # apply contact report
    ### This would be an example of each object managing their own collision
        self._contact_report_sub = get_physx_simulation_interface().subscribe_contact_report_events(self._on_contact_report_event)
        contactReportAPI = PhysxSchema.PhysxContactReportAPI.Apply(self.prim)
        contactReportAPI.CreateThresholdAttr().Set(self.contact_thresh)


    def _on_contact_report_event(self, contact_headers, contact_data):

        # Check if a collision was because of a player
        for contact_header in contact_headers:         
            collider_1 = str(PhysicsSchemaTools.intToSdfPath(contact_header.actor0))
            collider_2 = str(PhysicsSchemaTools.intToSdfPath(contact_header.actor1))

            contacts = [collider_1, collider_2]
            if  self.prim_path in contacts:
                self.object_path = ""
                if self.prim_path == collider_1:
                     self.object_path = collider_2
                else:
                     self.object_path = collider_1
                     print(collider_2)
                    
                if self.object_path in self.ignore_objects:
                        continue
                else:
                            self.ignore_objects.append(self.object_path)
                            self.pallet_collection += 1
                            print(f'Collected: {self.pallet_collection}')
                            self.collected_attr.Set(self.pallet_collection)