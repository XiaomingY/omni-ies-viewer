from pxr import Tf
from pxr import Gf
from pxr import Usd
from pxr import UsdGeom
from pxr import UsdShade
from pxr import UsdLux
from .IESReader import IESLight

import os.path
import numpy as np

from omni.ui import scene as sc
import omni.usd


def _flatten_matrix(matrix: Gf.Matrix4d):
    m0, m1, m2, m3 = matrix[0], matrix[1], matrix[2], matrix[3]
    return [
        m0[0],
        m0[1],
        m0[2],
        m0[3],
        m1[0],
        m1[1],
        m1[2],
        m1[3],
        m2[0],
        m2[1],
        m2[2],
        m2[3],
        m3[0],
        m3[1],
        m3[2],
        m3[3],
    ]

class ObjInfoModel(sc.AbstractManipulatorModel):
    """
    The model tracks the position and info of the selected object.
    """
    class MatrixItem(sc.AbstractManipulatorItem):
        """
        The Model Item represents the tranformation. It doesn't contain anything
        because we take the tranformation directly from USD when requesting.
        """

        identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]

        def __init__(self):
            super().__init__()
            self.value = self.identity.copy()

    class PositionItem(sc.AbstractManipulatorItem):
        """
        The Model Item represents the position. It doesn't contain anything
        because we take the position directly from USD when requesting.
        """
        def __init__(self) -> None:
            super().__init__()
            self.value = [0, 0, 0]

    class PositionList(sc.AbstractManipulatorItem):
        """
        The Model Item represents the position. It doesn't contain anything
        because we take the position directly from USD when requesting.
        """
        def __init__(self) -> None:
            super().__init__()
            self.value = [[0,0,0]]

    def __init__(self) -> None:
        super().__init__()

        # Current selected prim list
        self.prim = []
        self.current_path = []
        self.material_name = []

        self.stage_listener = None
        self.horizontal_step = 15
        self.vertical_step = 15

        self.IESPoints = [ObjInfoModel.PositionList()]
        self.transformation = [ObjInfoModel.MatrixItem()]

        # Save the UsdContext name (we currently only work with a single Context)
        self.usd_context = self._get_context()

        # Track selection changes
        self.events = self.usd_context.get_stage_event_stream()
        self.stage_event_delegate = self.events.create_subscription_to_pop(
            self.on_stage_event, name="Object Info Selection Update"
        )

    @property
    def _time(self):
        return Usd.TimeCode.Default()

    def _get_context(self) -> Usd.Stage:
        # Get the UsdContext we are attached to
        return omni.usd.get_context()
    
    #Update when light are transformed or modified
    def notice_changed(self, notice: Usd.Notice, stage: Usd.Stage) -> None:
        """Called by Tf.Notice.  Used when the current selected object changes in some way."""

        light_path = self.current_path
        if not light_path:
            return

        for p in notice.GetChangedInfoOnlyPaths():
            
            prim_path = p.GetPrimPath().pathString

            #check if prim_path not in selected list but parent of prim_path is in selected list
            if prim_path not in light_path:
                if (True in (light_path_item.startswith(prim_path) for light_path_item in light_path)):
                    if UsdGeom.Xformable.IsTransformationAffectedByAttrNamed(p.name):
                        self._item_changed(self.transformation[0])
                continue
            if UsdGeom.Xformable.IsTransformationAffectedByAttrNamed(p.name):
                self._item_changed(self.transformation[0])
            #if light property changed such as ies file changed, update profile
            self._item_changed(self.transformation[0])
            
    def _get_transform(self, time: Usd.TimeCode):
        """Returns world transform of currently selected object"""
        if not self.prim:
            return [ObjInfoModel.MatrixItem.identity.copy()]

        # Compute matrix from world-transform in USD
        #get transform matrix for each selected light
        world_xform_list = [UsdGeom.BasisCurves(prim).ComputeLocalToWorldTransform(time) for prim in self.prim]

        # Flatten Gf.Matrix4d to list
        return [_flatten_matrix(world_xform) for world_xform in world_xform_list]

    def get_item(self, identifier):
        if identifier == "IESPoints":
            return self.IESPoints
        if identifier == "transformation":
            return self.transformation

    def get_as_floats(self, item):
        if item == self.transformation:
            return self._get_transform(self._time)
        if item == self.IESPoints:
            return self.get_points(self._time)
        return []
    
    #get ies points for each selected light
    def get_points(self, time: Usd.TimeCode):
        if not self.prim:
            return [[0,0,0]]
        allIESPoint = []
        for prim in self.prim:
            iesFile = prim.GetAttribute('shaping:ies:file').Get()
            allIESPoint.append(IESLight(str(iesFile).replace('@', '')).points)
        return allIESPoint

    def on_stage_event(self, event):
        """Called by stage_event_stream.  We only care about selection changes."""
        if event.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
            self.current_path = []
            self.prim = []
            primList = []
            primPathList = []
            usd_context = self._get_context()
            stage = usd_context.get_stage()
            if not stage:
                return

            prim_paths = usd_context.get_selection().get_selected_prim_paths()

            if not prim_paths:
            # This turns off the manipulator when everything is deselected
                self._item_changed(self.transformation[0])
                return
            #select light with ies file applied.
            lightCount = 0
            for i in prim_paths:
                prim = stage.GetPrimAtPath(i)
                if(UsdLux.Light(prim) and prim.GetAttribute('shaping:ies:file').Get() and not (prim.IsA(UsdLux.DistantLight))):
                    primList.append(prim)
                    primPathList.append(i)
                    lightCount = lightCount +1
            if(lightCount==0):
                if self.stage_listener:
                    self.stage_listener.Revoke()
                    self.stage_listener = None
                self._item_changed(self.transformation[0])
                return

            if not self.stage_listener:
                # This handles camera movement
                self.stage_listener = Tf.Notice.Register(Usd.Notice.ObjectsChanged, self.notice_changed, stage)

            self.prim = primList
            self.current_path = primPathList
        # Position is changed because new selected object has a different position
            self._item_changed(self.transformation[0])

    def destroy(self):
        self.events = None
        self.stage_event_delegate.unsubscribe()