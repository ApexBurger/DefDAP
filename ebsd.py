import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.widgets import Button

import copy

from quat import Quat

#import ipyparallel as ipp

class Map(object):
    """Summary
    
    Attributes:
        averageSchmidFactor (TYPE): Description
        binData (TYPE): Description
        boundaries (TYPE): Description
        cacheEulerMap (TYPE): Description
        crystalSym (TYPE): Description
        currGrainId (TYPE): Description
        grainList (list): Description
        grains (TYPE): Description
        misOri (TYPE): Description
        misOriAxis (TYPE): Description
        misOx (TYPE): Description
        misOy (TYPE): Description
        quatArray (TYPE): Description
        smap (TYPE): Description
        stepSize (TYPE): Description
        xDim (TYPE): Description
        yDim (TYPE): Description
    """
    #defined instance variables
    #xDim, yDim - (int) dimensions of maps
    #binData - imported binary data
    
    def __init__(self, fileName, crystalSym):
        self.crystalSym = None  #symmetry of material e.g. "cubic", "hexagonal"
        self.xDim = None        #(int) dimensions of maps
        self.yDim = None
        self.stepSize = None   #(float) step size
        self.binData = None     #imported binary data
        self.quatArray = None   #(array) array of quaterions for each point of map
        self.misOx = None       #(array) map of misorientation with single neighbour pixel in positive x dir
        self.misOy = None
        self.boundaries = None  #(array) map of boundariers. -1 for a boundary, 0 otherwise
        self.grains = None      #(array) map of grains
        self.grainList = None   #(list) list of grains
        self.grainSizes = None  #(list) list of grain sizes (number of pixels in grain)
        self.misOri = None      #(array) map of misorientation
        self.misOriAxis = None  #(list of arrays) map of misorientation axis components
        self.averageSchmidFactor = None #(array) map of average Schmid factor
        self.currGrainId = None #Id of last selected grain
        self.origin = (0, 0)    #Map origin (y, x). Used by linker class where origin is a 
                                # homologue point of the maps
        self.homogPoints = None

        self.loadData(fileName, crystalSym)
        return
    
    def loadData(self, fileName, crystalSym):
        #open meta data file and read in x and y dimensions
        f = open(fileName + ".cpr", 'r')
        for line in f:
            if line[:6] == 'xCells':
                self.xDim = int(line[7:])
            if line[:6] == 'yCells':
                self.yDim = int(line[7:])
            if line[:9] == 'GridDistX':
                self.stepSize = float(line[10:])

                
        f.close()
        #now read the binary .crc file
        fmt_np=np.dtype([('Phase','b'), ('Eulers', [('ph1','f'), ('phi','f'), ('ph2','f')]),
                         ('mad','f'), ('IB2','uint8'), ('IB3','uint8'), ('IB4','uint8'),
                         ('IB5','uint8'), ('IB6','f')])
        self.binData = np.fromfile(fileName + ".crc", fmt_np, count=-1)
        self.crystalSym = crystalSym
        return
                         
    def plotBandContrastMap(self):
        self.checkDataLoaded()
                                 
        bcmap = np.reshape(self.binData[('IB2')], (self.yDim, self.xDim))
        plt.imshow(bcmap, cmap='gray')
        plt.colorbar()
        return

    def plotEulerMap(self, updateCurrent = False, highlightGrains = None):
        """Summary
        
        Args:
            updateCurrent (bool, optional): Description
            highlightGrains (List int, optional): Grain ids of grains to highlight
        """
        self.checkDataLoaded()

        if not updateCurrent:
            emap = np.transpose(np.array([self.binData['Eulers']['ph1'], self.binData['Eulers']['phi'],
                                      self.binData['Eulers']['ph2']]))
            #this is the normalization for the
            norm = np.tile(np.array([2*np.pi, np.pi/2, np.pi/2]), (self.yDim, self.xDim))
            norm = np.reshape(norm, (self.yDim,self.xDim,3))
            eumap = np.reshape(emap, (self.yDim,self.xDim,3))
            #make non-indexed points green
            eumap = np.where(eumap!=[0.,0.,0.], eumap, [0.,1.,0.])

            self.cacheEulerMap = eumap/norm
            self.fig, self.ax = plt.subplots()

        self.ax.imshow(self.cacheEulerMap, aspect='equal')

        if highlightGrains is not None: self.highlightGrains(highlightGrains)

        return

    def highlightGrains(self, grainIds):
        outline = np.zeros((self.yDim, self.xDim), dtype=int)
        for grainId in grainIds:
            #outline of highlighted grain
            grainOutline = self.grainList[grainId].grainOutline(bg = 0, fg = 1)
            x0, y0, xmax, ymax = self.grainList[grainId].extremeCoords()

            #use logical of same are in entire area to ensure neigbouring grains display correctly
            grainOutline = np.logical_or(outline[y0:ymax+1, x0:xmax+1], grainOutline).astype(int)
            outline[y0:ymax+1, x0:xmax+1] = grainOutline


        #Custom colour map where 0 is tranparent white for bg and 255 is opaque white for fg
        cmap1 = mpl.colors.LinearSegmentedColormap.from_list('my_cmap', ['white','white'], 256)
        cmap1._init()
        cmap1._lut[:,-1] = np.linspace(0, 1, cmap1.N+3)
        
        #plot highlighted grain overlay
        self.ax.imshow(outline, interpolation='none', vmin=0, vmax=1, cmap=cmap1)

        return


    def checkDataLoaded(self):
        if self.binData is None:
            raise Exception("Data not loaded")
        return
    
    def buildQuatArray(self):
        self.checkDataLoaded()
        
        if self.quatArray is None:
            self.quatArray = np.empty([self.yDim, self.xDim], dtype=Quat)
            for j in range(self.yDim):
                for i in range(self.xDim):
                    eulers = self.binData[j*self.xDim + i][('Eulers')]
                    self.quatArray[j, i] = Quat(eulers[0], eulers[1], eulers[2])
        return
    
    def findBoundaries(self, boundDef = 10):
        self.buildQuatArray()
        
        self.misOx = np.zeros((self.yDim, self.xDim))
        self.misOy = np.zeros((self.yDim, self.xDim))
        self.boundaries = np.zeros((self.yDim, self.xDim), dtype=int)
        
        
        #sweep in positive x and y dirs calculating misorientation with neighbour
        #if > boundDef then mark as a grain boundary
        for i in range(self.xDim):
            for j in range(self.yDim - 1):
                aux = abs(self.quatArray[j,i] % self.quatArray[j+1,i])
                if aux > 1:
                    aux = 1
                
                self.misOx[j,i] = 360 * np.arccos(aux) / np.pi
                
                if self.misOx[j,i] > boundDef:
                    self.misOx[j,i] = 0.0
                    self.boundaries[j,i] = -1
        
        
        for i in range(self.xDim - 1):
            for j in range(self.yDim):
                
                aux = abs(self.quatArray[j,i] % self.quatArray[j,i+1])
                if aux > 1:
                    aux = 1
                
                self.misOy[j,i] = 360 * np.arccos(aux) / np.pi
                
                if self.misOy[j,i] > boundDef:
                    self.misOy[j,i] = 0.0
                    self.boundaries[j,i] = -1
        
        return

    def plotBoundaryMap(self):
        plt.figure()
        plt.imshow(-self.boundaries, vmax=1)
        plt.colorbar()
        return
  
  
    def findGrains(self, minGrainSize = 10):
        #Initialise the grain map
        self.grains = np.copy(self.boundaries)
        
        self.grainList = []
        self.grainSizes = []

        #List of points where no grain has be set yet
        unknownPoints = np.where(self.grains == 0)
        #Start counter for grains
        grainIndex = 1
        
        #Loop until all points (except boundaries) have been assigned to a grain or ignored
        while unknownPoints[0].shape[0] > 0:
            #Flood fill first unknown point and return grain object
            currentGrain = self.floodFill(unknownPoints[1][0], unknownPoints[0][0], grainIndex)

            grainSize = len(currentGrain)
            if grainSize < minGrainSize:
                #if grain size less than minimum, ignore grain and set values in grain map to -2
                for coord in currentGrain.coordList:
                    self.grains[coord[1], coord[0]] = -2
            else:
                #add grain and size to lists and increment grain label
                self.grainList.append(currentGrain)
                self.grainSizes.append(grainSize)
                grainIndex += 1

            #update unknown points
            unknownPoints = np.where(self.grains == 0)
        return
            
    def plotGrainMap(self):
        plt.figure()
        plt.imshow(self.grains)
        plt.colorbar()
        return
    
    def locateGrainID(self, clickEvent = None):
        if (self.grainList is not None) and (self.grainList != []):
            #reset current selected grain and plot euler map with click handler
            self.currGrainId = None
            self.plotEulerMap()
            if clickEvent is None:
                #default click handler which highlights grain and prints id
                self.fig.canvas.mpl_connect('button_press_event', self.clickGrainId)
            else:
                #click handler loaded from linker classs. Pass current ebsd map to it.
                self.fig.canvas.mpl_connect('button_press_event', lambda x: clickEvent(x, self))

        else:
            raise Exception("Grain list empty")
            

    def clickGrainId(self, event):
        if event.inaxes is not None:
            #grain id of selected grain
            self.currGrainId = int(self.grains[int(event.ydata), int(event.xdata)] - 1)
            print self.currGrainId

            #clear current axis and redraw euler map with highlighted grain overlay
            self.ax.clear()
            self.plotEulerMap(updateCurrent = True, highlightGrains=[self.currGrainId])
            self.fig.canvas.draw()

            

    def floodFill(self, x, y, grainIndex):
        currentGrain = Grain(self.crystalSym)

        currentGrain.addPoint(self.quatArray[y, x], (x, y))
        
        edge = [(x, y)]
        grain = [(x, y)]
        
        self.grains[y, x] = grainIndex
        while edge:
            newedge = []
            
            for (x, y) in edge:
                moves = np.array([(x+1, y), (x-1, y), (x, y+1), (x, y-1)])
                
                movesIndexShift = 0
                if x <= 0:
                    moves = np.delete(moves, 1, 0)
                    movesIndexShift = 1
                elif x >= self.xDim-1:
                    moves = np.delete(moves, 0, 0)
                    movesIndexShift = 1
                
                if y <= 0:
                    moves = np.delete(moves, 3-movesIndexShift, 0)
                elif y >= self.yDim-1:
                    moves = np.delete(moves, 2-movesIndexShift, 0)
                
                
                for (s, t) in moves:
                    if self.grains[t, s] == 0:
                        currentGrain.addPoint(self.quatArray[t, s], (s, t))
                        newedge.append((s, t))
                        grain.append((s, t))
                        self.grains[t, s] = grainIndex
                    elif self.grains[t, s] == -1 and (s > x or t > y):
                        currentGrain.addPoint(self.quatArray[t, s], (s, t))
                        grain.append((s, t))
                        self.grains[t, s] = grainIndex
            
            if newedge == []:
                return currentGrain
            else:
                edge = newedge

    def calcGrainAvOris(self):
        for grain in self.grainList:
            grain.calcAverageOri()
        return

    def calcGrainMisOri(self, calcAxis = False):
        #localGrainList = self.grainList[0:10]

        #paraClient = ipp.Client()
        
        #dview = paraClient[:]
        #dview.map_sync(lambda x: x**10, range(32000000))
        #print dview.map_sync(lambda grain: grain.buildMisOriList(), localGrainList)
        
        #paraClient.close()
        
        for grain in self.grainList:
            grain.buildMisOriList(calcAxis = calcAxis)
        return

    def plotMisOriMap(self, component=0, plotGBs=False, vMin=None, vMax=None, cmap="viridis", cBarLabel="ROD (degrees)"):
        self.misOri = np.ones([self.yDim, self.xDim])
        
        plt.figure()
        
        if component in [1,2,3]:
            for grain in self.grainList:
                for coord, misOriAxis in zip(grain.coordList, np.array(grain.misOriAxisList)):
                    self.misOri[coord[1], coord[0]] = misOriAxis[component-1]
    
            plt.imshow(self.misOri * 180 / np.pi, interpolation='None', vmin=vMin, vmax=vMax, cmap=cmap)
    
        else:
            for grain in self.grainList:
                for coord, misOri in zip(grain.coordList, grain.misOriList):
                    self.misOri[coord[1], coord[0]] = misOri

            plt.imshow(np.arccos(self.misOri) * 360 / np.pi, interpolation='None', vmin=vMin, vmax=vMax, cmap=cmap)
    
        plt.colorbar(label = cBarLabel)

        if plotGBs:
            #create colourmap for boundaries and plot. colourmap goes transparent white to opaque black
            cmap1 = mpl.colors.LinearSegmentedColormap.from_list('my_cmap',['white','black'],256)
            cmap1._init()
            cmap1._lut[:,-1] = np.linspace(0, 1, cmap1.N+3)
            plt.imshow(-self.boundaries, interpolation='None', vmin=0, vmax=1, cmap=cmap1)

        return





    def calcAverageGrainSchmidFactors(self, loadVector = np.array([0, 0, 1])):
        for grain in self.grainList:
            grain.calcAverageSchmidFactors(loadVector = loadVector)
        return

    def buildAverageGrainSchmidFactorsMap(self):
        self.averageSchmidFactor = np.zeros([self.yDim, self.xDim])
        
        for grain in self.grainList:
            currentSchmidFactor = max(np.array(grain.averageSchmidFactors))
            for coord in grain.coordList:
                self.averageSchmidFactor[coord[1], coord[0]] = currentSchmidFactor
        return

    def plotAverageGrainSchmidFactorsMap(self):
        plt.figure()
        plt.imshow(self.averageSchmidFactor, interpolation='none')
        plt.colorbar()
        return








class Grain(object):
    
    def __init__(self, crystalSym):
        self.crystalSym = crystalSym    #symmetry of material e.g. "cubic", "hexagonal"
        self.coordList = []             #list of coords stored as tuples (x, y)
        self.quatList = []              #list of quats
        self.misOriList = None          #list of misOri at each point in grain
        self.misOriAxisList = None      #list of misOri axes at each point in grain
        self.refOri = None              #(quat) average ori of grain
        self.averageMisOri = None       #average misOri of grain
        
        self.loadVectorCrystal = None   #load vector in crystal coordinates
        self.averageSchmidFactors = None    #list of Schmid factors for each system
        return
    
    def __len__(self):
        return len(self.quatList)
    
    #quat is a quaterion and coord is a tuple (x, y)
    def addPoint(self, quat, coord):
        self.coordList.append(coord)
        self.quatList.append(quat)
        return

    def calcAverageOri(self):
        firstQuat = True
        self.refOri = copy.deepcopy(self.quatList[0])  #start average
        for quat in self.quatList[1:]:
            #loop over symmetries and find min misorientation for average
            #add the symetric equivelent of quat with the minimum misorientation (relative to the average)
            #to the average. Then normalise.
            self.refOri += self.refOri.misOri(quat, self.crystalSym, returnQuat = 1)
        self.refOri.normalise()
        return

    def buildMisOriList(self, calcAxis = False):
        if self.refOri is None:
            self.calcAverageOri()


        self.misOriList = []
        
        if calcAxis:
            self.misOriAxisList = []
            aveageOriInverse = self.refOri.conjugate()
        
        for quat in self.quatList:
            #Calculate misOri to average ori. Return closest symmetric equivalent for later use
            currentMisOri, currentQuatSym = self.refOri.misOri(quat, self.crystalSym, returnQuat = 2)
            if currentMisOri > 1:
                currentMisOri = 1
            self.misOriList.append(currentMisOri)
            
            
            if calcAxis:
                #Calculate misorientation axis
                Dq = aveageOriInverse * currentQuatSym #definately quaternion product?
                self.misOriAxisList.append((2 * Dq[1:4] * np.arccos(Dq[0])) / np.sqrt(1 - np.power(Dq[0], 2)))


        self.averageMisOri = np.array(self.misOriList).mean()
        
        return
        #return self#to make it work with parallel
    
    
    
    def extremeCoords(self):
        unzippedCoordlist = list(zip(*self.coordList))
        x0 = min(unzippedCoordlist[0])
        y0 = min(unzippedCoordlist[1])
        xmax = max(unzippedCoordlist[0])
        ymax = max(unzippedCoordlist[1])
        return x0, y0, xmax, ymax

    def grainOutline(self, bg = np.nan, fg = 0):
        x0, y0, xmax, ymax = self.extremeCoords()
    
        #initialise array with nans so area not in grain displays white
        outline = np.full((ymax - y0 + 1, xmax - x0 + 1), bg, dtype=int)

        for coord in self.coordList:
            outline[coord[1] - y0, coord[0] - x0] = fg

        return outline

    def plotOutline(self):
        plt.figure()
        plt.imshow(self.grainOutline(), interpolation='none')
        plt.colorbar()
        
        return
    
    
    #component
    #0 = misOri
    #{1-3} = misOri axis {1-3}
    #4 = all
    #5 = all axis
    def plotMisOri(self, component=0, vMin=None, vMax=None, vRange=[None, None, None], cmap=["viridis", "bwr"]):
        component = int(component)
        
        x0, y0, xmax, ymax = self.extremeCoords()
        
        if component in [4, 5]:
            #subplots
            grainMisOri = np.full((4, ymax - y0 + 1, xmax - x0 + 1), np.nan, dtype=float)
            
            for coord, misOri, misOriAxis in zip(self.coordList,
                                                 np.arccos(self.misOriList) * 360 / np.pi,
                                                 np.array(self.misOriAxisList) * 180 / np.pi):
                grainMisOri[0, coord[1] - y0, coord[0] - x0] = misOri
                grainMisOri[1:4, coord[1] - y0, coord[0] - x0] = misOriAxis
            
            f, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2)
            
            img = ax1.imshow(grainMisOri[0], interpolation='none', cmap=cmap[0], vmin=vMin, vmax=vMax)
            plt.colorbar(img, ax=ax1)
            vmin = None if vRange[0] is None else -vRange[0]
            img = ax2.imshow(grainMisOri[1], interpolation='none', cmap=cmap[1], vmin=vmin, vmax=vRange[0])
            plt.colorbar(img, ax=ax2)
            vmin = None if vRange[0] is None else -vRange[1]
            img = ax3.imshow(grainMisOri[2], interpolation='none', cmap=cmap[1], vmin=vmin, vmax=vRange[1])
            plt.colorbar(img, ax=ax3)
            vmin = None if vRange[0] is None else -vRange[2]
            img = ax4.imshow(grainMisOri[3], interpolation='none', cmap=cmap[1], vmin=vmin, vmax=vRange[2])
            plt.colorbar(img, ax=ax4)
                
            
        else:
            #single plot
            #initialise array with nans so area not in grain displays white
            grainMisOri = np.full((ymax - y0 + 1, xmax - x0 + 1), np.nan, dtype=float)
        
            if component in [1,2,3]:
                plotData = np.array(self.misOriAxisList)[:, component-1] * 180 / np.pi
            else:
                plotData = np.arccos(self.misOriList) * 360 / np.pi
        
            for coord, misOri in zip(self.coordList, plotData):
                grainMisOri[coord[1] - y0, coord[0] - x0] = misOri

            plt.figure()
            plt.imshow(grainMisOri, interpolation='none', vmin=vMin, vmax=vMax, cmap=cmap[0])
            plt.colorbar()

        return
    
    
    
    
    
    
    #define load axis as unit vector
    def calcAverageSchmidFactors(self, loadVector = np.array([0, 0, 1])):
        if self.refOri is None:
            self.calcAverageOri()
        
        #Transform the load vector into crystal coordinates
        loadQuat = Quat(0, loadVector[0], loadVector[1], loadVector[2])

        loadQuatCrystal = (self.refOri * loadQuat) * self.refOri.conjugate()
    
        loadVectorCrystal = loadQuatCrystal[1:4]    #will still be a unit vector as aveageOri is a unit quat
        self.loadVectorCrystal = loadVectorCrystal
        
        self.averageSchmidFactors = []
    
        #calculated Schmid factor of average ori with all slip systems
        for slipSystem in self.slipSystems():
            self.averageSchmidFactors.append(abs(np.dot(loadVectorCrystal, slipSystem[1])
                                                 * np.dot(loadVectorCrystal, slipSystem[0])))


    #slip systems defined as list with 1st value the slip direction, 2nd the slip plane and 3rd a label
    #define as unit vectors
    def slipSystems(self):
        systems = []
        if self.crystalSym == "cubic":
            systems.append([
                np.array([0, 0.707107, -0.707107]), 
                np.array([0.577350, 0.577350, 0.577350]), 
                "(111)[01-1]"
                ])
            systems.append([
                np.array([-0.707107, 0, 0.707107]), 
                np.array([0.577350, 0.577350, 0.577350]), 
                "(111)[-101]"
                ])
            systems.append([
                np.array([0.707107, -0.707107, 0]), 
                np.array([0.577350, 0.577350, 0.577350]), 
                "(111)[1-10]"
                ])

            systems.append([
                np.array([0, 0.707107, 0.707107]), 
                np.array([0.577350, 0.577350, -0.577350]), 
                "(11-1)[011]"])
            systems.append([
                np.array([-0.707107, 0, -0.707107]), 
                np.array([0.577350, 0.577350, -0.577350]), 
                "(11-1)[-10-1]"])
            systems.append([
                np.array([0.707107, -0.707107, 0]), 
                np.array([0.577350, 0.577350, -0.577350]), 
                "(11-1)[1-10]"])

            systems.append([
                np.array([0, 0.707107, -0.707107]), 
                np.array([-0.577350, 0.577350, 0.577350]), 
                "(-111)[01-1]"])
            systems.append([
                np.array([0.707107, 0, 0.707107]), 
                np.array([-0.577350, 0.577350, 0.577350]), 
                "(-111)[101]"])
            systems.append([
                np.array([-0.707107, -0.707107, 0]), 
                np.array([-0.577350, 0.577350, 0.577350]), 
                "(-111)[-1-10]"])

            systems.append([
                np.array([0, -0.707107, -0.707107]), 
                np.array([0.577350, -0.577350, 0.577350]), 
                "(1-11)[0-1-1]"])
            systems.append([
                np.array([-0.707107, 0, 0.707107]), 
                np.array([0.577350, -0.577350, 0.577350]), 
                "(1-11)[-101]"])
            systems.append([
                np.array([0.707107, 0.707107, 0]), 
                np.array([0.577350, -0.577350, 0.577350]), 
                "(1-11)[110]"])

        return systems




class Linker(object):

    def __init__(self, maps):
        self.ebsdMaps = maps
        self.numMaps = len(maps)
        self.links = []
        return

    def setOrigin(self):
        for ebsdMap in self.ebsdMaps:
            ebsdMap.locateGrainID(clickEvent = self.clickSetOrigin)

    def clickSetOrigin(self, event, currentEbsdMap):
        currentEbsdMap.origin = (int(event.ydata), int(event.xdata))
        print "Origin set to ({:}, {:})".format(currentEbsdMap.origin[0], currentEbsdMap.origin[1])

    def startLinking(self):
        for ebsdMap in self.ebsdMaps:
            ebsdMap.locateGrainID(clickEvent = self.clickGrainGuess)

            #Add make link button to axes
            btnAx = ebsdMap.fig.add_axes([0.8, 0.0, 0.1, 0.07])
            
            btnLink = Button(btnAx, 'Make link', color='0.85', hovercolor='0.95')


    def clickGrainGuess(self, event, currentEbsdMap):
        #self is cuurent linker instance even if run as click event handler from map class
        if event.inaxes is currentEbsdMap.fig.axes[0]:
            #axis 0 then is a click on the map

            if currentEbsdMap is self.ebsdMaps[0]:
                #clicked on 'master' map so highlight and guess grain on other maps
                for ebsdMap in self.ebsdMaps:
                    if ebsdMap is currentEbsdMap:
                        #set current grain in ebsd map that clicked
                        ebsdMap.clickGrainId(event)
                    else:
                        #Guess at grain in other maps
                        #Calculated position relative to set origin of the map, scaled from step size of maps
                        y0m = currentEbsdMap.origin[0]
                        x0m = currentEbsdMap.origin[1]
                        y0 = ebsdMap.origin[0]
                        x0 = ebsdMap.origin[1]
                        scaling = currentEbsdMap.stepSize / ebsdMap.stepSize

                        x = int((event.xdata - x0m)*scaling + x0)
                        y = int((event.ydata - y0m)*scaling + y0)

                        ebsdMap.currGrainId = int(ebsdMap.grains[y, x]) - 1
                        print ebsdMap.currGrainId

                        #clear current axis and redraw euler map with highlighted grain overlay
                        ebsdMap.ax.clear()
                        ebsdMap.plotEulerMap(updateCurrent = True, highlightGrains=[ebsdMap.currGrainId])
                        ebsdMap.fig.canvas.draw()
            else:
                #clicked on other map so correct guessed selected grain
                currentEbsdMap.clickGrainId(event)

        elif event.inaxes is currentEbsdMap.fig.axes[1]:
            #axis 1 then is a click on the button
            self.makeLink()


    def makeLink(self):
        #create empty list for link
        currLink = []

        for i, ebsdMap in enumerate(self.ebsdMaps):
            if ebsdMap.currGrainId is not None:
                currLink.append(ebsdMap.currGrainId)
            else:
                raise Exception("No grain setected in map {:d}.".format(i+1))

        self.links.append(tuple(currLink))

        print "Link added " + str(tuple(currLink))

    def resetLinks(self):
        self.links = []




    def setAvOriFromInitial(self):
        masterMap = self.ebsdMaps[0]

        #loop over each map (not first/refernece) and each link. Set refOri of linked grains
        #to refOri of grain in first map
        for i, ebsdMap in enumerate(self.ebsdMaps[1:], start = 1):
            for link in self.links:
                ebsdMap.grainList[link[i]].refOri = copy.deepcopy(masterMap.grainList[link[0]].refOri)

        return

    def updateMisOri(self, calcAxis = False):
        #recalculate misorientation for linked grain (not for first map)
        for i, ebsdMap in enumerate(self.ebsdMaps[1:], start = 1):
            for link in self.links:
                ebsdMap.grainList[link[i]].buildMisOriList(calcAxis = calcAxis)

        return














