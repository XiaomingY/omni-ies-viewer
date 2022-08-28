import numpy as np
import re
import math
#import matplotlib.pyplot as plt
from scipy import interpolate
import os.path
#from mpl_toolkits.mplot3d.axes3d import Axes3D
import omni.ext
import omni.ui as ui
omni.kit.pipapi.install("astropy")
from astropy.coordinates import spherical_to_cartesian

DEFAULT_HORIZONTAL_STEP = 15
DEFAULT_VERTICAL_STEP = 15
IES_MaxLength = 80

class IESLight():
    def __init__(self,iesFile):

        # Current selected prim
        if iesFile and os.path.exists(iesFile):
            self.file = iesFile
        else:
            return
        self.width = 0
        self.length = 0
        self.radius = 0
        all_values = self.readIESfile(self.file)
        verticalAngles,horizontalAngles,intensities,self.width,self.length,self.radius = self.getIESproperties(all_values)
        horizontalAnglesMirrored, intensityMirrored = self.mirrorAngles(horizontalAngles,intensities)
        horizontalResampled = np.arange(0, 361, DEFAULT_HORIZONTAL_STEP)
        verticalResampled = np.arange(0, verticalAngles[-1]+1, DEFAULT_VERTICAL_STEP)
        resampledIntensity = self.interpolateIESValues(np.array(horizontalAnglesMirrored),np.array(verticalAngles),horizontalResampled,verticalResampled,intensityMirrored)
        self.points = self.IESCoord2XYZ(horizontalResampled,verticalResampled,resampledIntensity,IES_MaxLength)
    #read ies files and return vertical angles, horizontal angles, intensities, width, length, radius.
    #based on the symmetry, horizontal angles and resampled
    def readIESfile(self, fileName):
        f=open(fileName, encoding = "ISO-8859-1")#need rb to read \r\n correctly. Otherwise universial newline function ignores carriage return.     
        startReading = 0
        line = f.readline()
        allValues = ""
        while line:       
            if( not(line.strip())):
                break
            else:
                #after this line, there are actual useful values
                if("TILT=NONE" in line.strip()):
                    line = f.readline()
                    startReading = 1
                #read all number to one string
                if(startReading):
                    allValues = allValues+line
                    
                line = f.readline()

        f.close()
        #one array with all values
        dimentions = re.split('\s+',allValues.strip())
        return dimentions
    
    def getIESproperties(self, allValues):
        #return 
        FEET2METER = 0.3048
        verticalAngles = []
        horizontalAngles = []
        width = 0
        length = 0
        radius = 0
        intensityMultiplier = 1
        numberVerticalAngle = 0
        numberHorizontalAngle = 0
        unit = 1 #1 for feet, 2 for meter
        
        #number of vertical angles and horizontal angles measured
        numberVerticalAngle = int(allValues[3])
        numberHorizontalAngle = int(allValues[4])
        
        #check if shape is rectangle or disk
        if(float(allValues[7])<0):
            radius = allValues[7]*-1
        else:
            width = allValues[7]
            length = allValues[8]
        #convert dimentions to meter if measured in feet
        if(float(allValues[6])==1):
            radius = radius*FEET2METER
            width = width *FEET2METER
            length = length * FEET2METER
        
        #the actual vertical angles and horizontal angles in list
        verticalAngles = list(map(float, allValues[13:13+numberVerticalAngle]))
        horizontalAngles = list(map(float,allValues[13+numberVerticalAngle:13+numberVerticalAngle+numberHorizontalAngle]))
        
        #read intensities and convert it to 2d array
        intensities = np.array(allValues[13+numberVerticalAngle+numberHorizontalAngle:len(allValues)])
        intensities = intensities.reshape(numberHorizontalAngle,numberVerticalAngle).astype(np.float16)
        
        return verticalAngles,horizontalAngles,intensities,width,length,radius

    #ies could have several symmetry:
    #(1)only measured in one horizontal angle (0) which need to be repeated to all horizontal angle from 0 to 360
    #(2)only measured in horizontal angles (0~90) which need to be mirrored twice to horizontal angle from 0 to 360
    #(3)only measured in horizontal angles (0~180) which need to be mirrored to horizontal angle from 0 to 360
    #(4)only measured in horizontal angles (0~360) which could be used directly
    def mirrorAngles(self, horizontalAngles,intensities):
        #make use of symmetry in the file and produce horizontal angles from 0~360
        if(horizontalAngles[-1]==0):
            horizontalAnglesMirrored = list(np.arange(0,361,DEFAULT_HORIZONTAL_STEP))
        else:
            horizontalAnglesMirrored = list(np.arange(0,361,horizontalAngles[-1]/(len(horizontalAngles)-1)))
        
        #make use of symmetry in the file and copy intensitys for horizontal angles from 0~360
        if(horizontalAngles[-1]==90):
            #mirror results [90:180]
            a = np.concatenate((intensities, np.flip(intensities, 0)[1:]), axis=0)
            intensityMirrored = np.concatenate((a, np.flip(a, 0)[1:]), axis=0)
        elif(horizontalAngles[-1]==180):
            intensityMirrored = np.concatenate((intensities, np.flip(intensities, 0)[1:]), axis=0)
        elif(horizontalAngles[-1]==0):
            intensityMirrored = np.array(([intensities[0],]*len(np.arange(0,361,DEFAULT_HORIZONTAL_STEP))))
        else:
        #print("Symmetry 360")
            intensityMirrored = intensities

        return horizontalAnglesMirrored, intensityMirrored
    
    def IESCoord2XYZ(self, horizontalAngles,verticalAngles,intensity,maxLength):
        maxValue = np.amax(intensity)
        if(maxValue>maxLength):
            intensity = intensity*(maxLength/maxValue)
        for index, horizontalAngle in  enumerate(horizontalAngles):
            if(index ==0):
                #Omniverse and 3ds Max makes the light upside down, horizontal angle rotation direction need to be flipped.
                points = np.array(spherical_to_cartesian(intensity[index].tolist(), [math.radians(90-x) for x in verticalAngles], [math.radians(-1*horizontalAngle)]*len(verticalAngles))).transpose()
            else:
                newPoints = np.array(spherical_to_cartesian(intensity[index], [math.radians(90-x) for x in verticalAngles], [math.radians(-1*horizontalAngle)]*len(verticalAngles))).transpose()
                points = np.concatenate((points, newPoints), axis=0)
        #Omniverse and 3ds Max makes the light upside down, so flip z.
        points[:,2] *= -1
        return points
    
    def interpolateIESValues(self, originalHorizontalAngles, originalVerticalAngles, newHorizontalAngles,newVerticalAngles, intensity):
        fun = interpolate.interp2d(originalVerticalAngles, originalHorizontalAngles, intensity, kind='linear') # kind could be {'linear', 'cubic', 'quintic'}
        interpolatedIntensity = fun(newVerticalAngles,newHorizontalAngles)
        return interpolatedIntensity