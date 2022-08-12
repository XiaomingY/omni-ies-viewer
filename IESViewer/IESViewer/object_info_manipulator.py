from __future__ import division
from omni.ui import scene as sc
from omni.ui import color as cl
import omni.ui as ui
import numpy as np

class ObjInfoManipulator(sc.Manipulator):
    """Manipulator that displays the object path and material assignment
    with a leader line to the top of the object's bounding box.
    """
    def on_build(self):
        """Called when the model is changed and rebuilds the whole manipulator"""
    
        if not self.model:
            return

        IESPoints = self.model.get_as_floats(self.model.IESPoints)

        numHorizontal = int((360/self.model.horizontal_step)+1)
        primCount = 0

        for transformation in self.model.get_as_floats(self.model.transformation):
            self.__root_xf = sc.Transform(transformation)

            with self.__root_xf:
                self._x_xform = sc.Transform()
                with self._x_xform:
                    self._shape_xform = sc.Transform()
                    
                    IESPoint = IESPoints[primCount]
                    numVertical = int(len(IESPoint)/numHorizontal)
                    for index in range(0,numHorizontal):
                        points = IESPoint[index*numVertical:(index+1)*numVertical]
                        if(len(points)>0):
                            sc.Curve(points.tolist(), thicknesses=[1.0], colors=[cl.yellow],tessellation=9)
                    primCount = primCount+1
    
    def on_model_updated(self, item):
    # Regenerate the manipulator
        self.invalidate()