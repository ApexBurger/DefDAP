import numpy as np

from defdap import plotting


class Map(object):

    def __init__(self):
        self.grainList = None
        self.homogPoints = []

        self.proxigramArr = None

        self.grainPlot = None

    def __len__(self):
        return len(self.grainList)

    # allow array like getting of grains
    def __getitem__(self, key):
        # Check that grains have been detected in the map
        self.checkGrainsDetected()

        return self.grainList[key]

    def checkGrainsDetected(self):
        """Check if grains have been detected

        Returns:
            bool: Returns True if grains detected

        Raises:
            Exception: if grains not detected
        """
        if self.grainList is None or type(self.grainList) is not list or len(self.grainList) < 1:
            raise Exception("No grains detected.")
        return True

    def plotGrainNumbers(self, dilateBoundaries=False, ax=None, **kwargs):
        """Plot a map with grains numbered

        Args:
            dilateBoundaries(bool, optional): Set to true to dilate
            boundaries by one pixel
        """
        plot = plotting.MapPlot(self, ax=ax)
        plot.addGrainBoundaries(colour='black', dilate=dilateBoundaries)
        plot.addGrainNumbers(**kwargs)

        return plot

    def locateGrainID(self, clickEvent=None, displaySelected=False, **kwargs):
        """
        Interactive plot for identifying grains

        :param displaySelected: Plot slip traces for selected grain
        """
        # Check that grains have been detected in the map
        self.checkGrainsDetected()

        # reset current selected grain and plot euler map with click handler
        self.currGrainId = None
        plot = self.plotDefault(makeInteractive=True, **kwargs)
        if clickEvent is None:
            # default click handler which highlights grain and prints id
            plot.addEventHandler(
                'button_press_event',
                lambda e, p: self.clickGrainID(e, p, displaySelected)
            )
        else:
            # click handler loaded in as parameter. Pass current map
            # object to it.
            plot.addEventHandler('button_press_event', clickEvent)

        # if displaySelected:
        #     self.grainPlot =

        return plot

    def clickGrainID(self, event, plot, displaySelected):
        if event.inaxes is plot.ax:
            # grain id of selected grain
            self.currGrainId = int(self.grains[int(event.ydata), int(event.xdata)] - 1)
            print("Grain ID: {}".format(self.currGrainId))

            # update the grain highlights layer in the plot
            plot.addGrainHighlights([self.currGrainId], alpha=self.highlightAlpha)

            # TODO: Check display selected works for ebsd map
            if displaySelected:
                currGrain = self[self.currGrainId]
                if self.grainPlot is None or not self.grainPlot.exists:
                    self.grainPlot = currGrain.plotDefault(makeInteractive=True)
                else:
                    self.grainPlot.clear()
                    currGrain.plotDefault(plot=self.grainPlot)

    def setHomogPoint(self, binSize=1, points=None):
        if points is None:
            plot = self.plotHomog(makeInteractive=True)
            # Plot stored homogo points if there are any
            if len(self.homogPoints) > 0:
                homogPoints = np.array(self.homogPoints) * binSize
                plot.addPoints(homogPoints[:, 0], homogPoints[:, 1], c='y', s=60)
            else:
                # add empty points layer to update later
                plot.addPoints([None], [None], c='y', s=60)

            # add empty points layer for current selected point
            plot.addPoints([None], [None], c='w',s=60, marker='x')

            plot.addEventHandler('button_press_event', self.clickHomog)

            plot.addButton(
                "Save point",
                lambda e, p: self.clickSaveHomog(e, p, binSize),
                color="0.85", hovercolor="blue"
            )
        else:
            self.homogPoints = points

    def clickHomog(self, event, plot):
        if event.inaxes is plot.ax:
            plot.addPoints([int(event.xdata)], [int(event.ydata)], updateLayer=1)

    def clickSaveHomog(self, event, plot, binSize):
        # get the selected point
        points = plot.imgLayers[plot.pointsLayerIDs[1]]
        selPoint = points.get_offsets()[0]

        # Check if a point is selected
        if selPoint[0] is not None and selPoint[1] is not None:
            # remove selected point from plot
            plot.addPoints([None], [None], updateLayer=1)

            # then scale and add to homog points list
            selPoint = tuple((selPoint / binSize).round().astype(int))
            self.homogPoints.append(selPoint)

            # update the plotted homog points
            homogPoints = np.array(self.homogPoints) * binSize
            plot.addPoints(homogPoints[:, 0], homogPoints[:, 1], updateLayer=0)

    def updateHomogPoint(self, homogID, newPoint=None, delta=None):
        """Update a homog by either over wrting it with a new point or
        incrementing the current values.

        Args:
            homogID (int): ID (place in list) of point to update or -1 for all
            newPoint (tuple, optional): New point
            delta (tuple, optional): Increments to current point (dx, dy)
        """
        if type(homogID) is not int:
            raise Exception("homogID must be an integer.")
        if homogID >= len(self.homogPoints):
            raise Exception("homogID is out of range.")

        # Update all points
        if homogID < 0:
            for i in range(len(self.homogPoints)):
                self.updateHomogPoint(homogID=i, delta=delta)
        # Update a single point
        else:
            # overwrite point
            if newPoint is not None:
                if type(newPoint) is not tuple and len(newPoint) != 2:
                    raise Exception("newPoint must be a 2 component tuple")

            # increment current point
            elif delta is not None:
                if type(delta) is not tuple and len(delta) != 2:
                    raise Exception("delta must be a 2 component tuple")
                newPoint = list(self.homogPoints[homogID])
                newPoint[0] += delta[0]
                newPoint[1] += delta[1]
                newPoint = tuple(newPoint)

            self.homogPoints[homogID] = newPoint

    def buildNeighbourNetwork(self):
        # Construct a list of neighbours

        yLocs, xLocs = np.nonzero(self.boundaries)
        neighboursList = []

        for y, x in zip(yLocs, xLocs):
            if x == 0 or y == 0 or x == self.grains.shape[1] - 1 or y == self.grains.shape[0] - 1:
                # exclude boundary pixel of map
                continue
            else:
                # use sets as they do not allow duplicate elements
                # minus 1 on all as the grain image starts labeling at 1
                neighbours = {self.grains[y + 1, x] - 1, self.grains[y - 1, x] - 1,
                              self.grains[y, x + 1] - 1, self.grains[y, x - 1] - 1}
                # neighbours = set(neighbours)
                # remove boundary points (-2) and points in small grains (-3) (Normally -1 and -2)
                neighbours.discard(-2)
                neighbours.discard(-3)

                nunNeig = len(neighbours)

                if nunNeig == 1:
                    continue
                elif nunNeig == 2:
                    neighboursSplit = [neighbours]
                elif nunNeig > 2:
                    neighbours = list(neighbours)
                    neighboursSplit = []
                    for i in range(nunNeig):
                        for j in range(i + 1, nunNeig):
                            neighboursSplit.append({neighbours[i], neighbours[j]})

                for trialNeig in neighboursSplit:
                    if trialNeig not in neighboursList:
                        neighboursList.append(trialNeig)

        # create network
        import networkx as nx
        self.neighbourNetwork = nx.Graph()
        self.neighbourNetwork.add_nodes_from(range(len(self)))
        self.neighbourNetwork.add_edges_from(neighboursList)

    def displayNeighbours(self):
        self.locateGrainID(clickEvent=self.clickGrainNeighbours)

    def clickGrainNeighbours(self, event, plot):
        if event.inaxes is plot.ax:
            # grain id of selected grain
            grainId = int(self.grains[int(event.ydata), int(event.xdata)] - 1)
            if grainId < 0:
                return
            self.currGrainId = grainId

            # find first and second nearest neighbours
            firstNeighbours = list(self.neighbourNetwork.neighbors(self.currGrainId))

            secondNeighbours = []
            for firstNeighbour in firstNeighbours:
                trialSecondNeighbours = list(self.neighbourNetwork.neighbors(firstNeighbour))
                for secondNeighbour in trialSecondNeighbours:
                    if (secondNeighbour not in highlightGrains and
                            secondNeighbour not in secondNeighbours):
                        secondNeighbours.append(secondNeighbour)
            highlightGrains.extend(secondNeighbours)

            highlightGrains = [self.currGrainId] + firstNeighbours + secondNeighbours
            highlightColours = ['white']
            highlightColours.extend(['yellow'] * len(firstNeighbours))
            highlightColours.append('green')

            # update the grain highlights layer in the plot
            plot.addGrainHighlights(highlightGrains, grainColours=highlightColours)

    @property
    def proxigram(self):
        self.calcProxigram(forceCalc=False)

        return self.proxigramArr

    def calcProxigram(self, numTrials=500, forceCalc=True):
        if self.proxigramArr is not None and not forceCalc:
            return

        proxBoundaries = np.copy(self.boundaries)
        proxShape = proxBoundaries.shape

        # ebsd boundary arrays have extra boundary along right and bottom edge. These need to be removed
        # rigth edge
        if np.all(proxBoundaries[:, -1] == -1):
            proxBoundaries[:, -1] = proxBoundaries[:, -2]
        # bottom edge
        if np.all(proxBoundaries[-1, :] == -1):
            proxBoundaries[-1, :] = proxBoundaries[-2, :]

        # create list of positions of each boundary point
        indexBoundaries = []
        for index, value in np.ndenumerate(proxBoundaries):
            if value == -1:
                indexBoundaries.append(index)
        # add 0.5 to boundary coordiantes as they are placed on the
        # bottom right edge pixels of grains
        indexBoundaries = np.array(indexBoundaries) + 0.5

        # array of x and y coordinate of each pixel in the map
        coords = np.zeros((2, proxShape[0], proxShape[1]), dtype=float)
        coords[0], coords[1] = np.meshgrid(range(proxShape[0]), range(proxShape[1]), indexing='ij')

        # array to store trial distance from each boundary point
        trialDistances = np.full((numTrials + 1, proxShape[0], proxShape[1]), 1000, dtype=float)

        # loop over each boundary point (p) and calculate distance from
        # p to all points in the map store minimum once numTrails have
        # been made and start a new batch of trials
        print("Calculating proxigram ", end='')
        numBoundaryPoints = len(indexBoundaries)
        j = 1
        for i, indexBoundary in enumerate(indexBoundaries):
            trialDistances[j] = np.sqrt((coords[0] - indexBoundary[0])**2 + (coords[1] - indexBoundary[1])**2)

            if j == numTrials:
                # find current minimum distances and store
                trialDistances[0] = trialDistances.min(axis=0)
                j = 0
                print("{:.1f}% ".format(i / numBoundaryPoints * 100), end='')
            j += 1

        # find final minimum distances to a boundary
        self.proxigramArr = trialDistances.min(axis=0)

        trialDistances = None


class Grain(object):

    def __init__(self):
        # list of coords stored as tuples (x, y). These are coords in a
        # cropped image if crop exists.
        self.coordList = []

    def __len__(self):
        return len(self.coordList)

    @property
    def extremeCoords(self):
        coords = np.array(self.coordList, dtype=int)

        x0, y0 = coords.min(axis=0)
        xmax, ymax = coords.max(axis=0)

        return x0, y0, xmax, ymax

    def centreCoords(self, centreType="box", grainCoords=True):
        """
        Calculates the centre of the grain, either as the centre of the
        bounding box or the grains centre of mass.

        Parameters
        ----------
        centreType : str, optional, {'box', 'com'}
            Set how to calculate the centre. Either 'box' for centre of
            boundiing box or 'com' for centre of mass. Default is 'box'.
        grainCoords : bool, optional
            If set True the centre is returned in the grain coordinates
            otherwise in the map coordinates. Defaults is grain.

        Returns
        -------
        int, int
            Coordinates of centre of grain
        """
        x0, y0, xmax, ymax = self.extremeCoords
        if centreType == "box":
            xCentre = round((xmax + x0) / 2)
            yCentre = round((ymax + y0) / 2)
        elif centreType == "com":
            xCentre, yCentre = np.array(self.coordList).mean(axis=0).round()
        else:
            raise ValueError("centreType must be box or com")

        if grainCoords:
            xCentre -= x0
            yCentre -= y0

        return int(xCentre), int(yCentre)

    def grainOutline(self, bg=np.nan, fg=0):
        x0, y0, xmax, ymax = self.extremeCoords

        # initialise array with nans so area not in grain displays white
        outline = np.full((ymax - y0 + 1, xmax - x0 + 1), bg, dtype=int)

        for coord in self.coordList:
            outline[coord[1] - y0, coord[0] - x0] = fg

        return outline

    def plotOutline(self, ax=None, plotScaleBar=False, **kwargs):
        plot = plotting.GrainPlot(self, ax=ax)
        plot.addMap(self.grainOutline(), **kwargs)

        if plotScaleBar:
            plot.addScaleBar()

        return plot

    def grainData(self, mapData):
        """
        Extract this grains data from the given map data.

        Parameters
        ----------
        mapData : numpy.ndarray
            Array of map data. This must be cropped!

        Returns
        -------
        numpy.ndarray
            Array containing this grains values from the given map data.
        """
        grainData = np.zeros(len(self), dtype=mapData.dtype)

        for i, coord in enumerate(self.coordList):
            grainData[i] = mapData[coord[1], coord[0]]

        return grainData

    def grainMapData(self, mapData, bg=np.nan):
        """
        Extract a single grain map from the given map data.

        Parameters
        ----------
        mapData : numpy.ndarray
            Array of map data. This must be cropped!
        bg : various, optional
            Value to fill the backgraound with. Must be same dtype as
            input array.

        Returns
        -------
        numpy.ndarray
            Grain map extracted from given data.
        """
        grainData = self.grainData(mapData)
        x0, y0, xmax, ymax = self.extremeCoords

        grainMapData = np.full((ymax - y0 + 1, xmax - x0 + 1), bg, dtype=mapData.dtype)

        for coord, data in zip(self.coordList, grainData):
            grainMapData[coord[1] - y0, coord[0] - x0] = data

        return grainMapData

    def grainMapDataCoarse(self, mapData, kernelSize=2, bg=np.nan):
        """
        Create a coarsed data map of this grain only from the given map
        data. Data is coarsened using a kenel at each pixel in the
        grain using only data in this grain.

        Parameters
        ----------
        mapData : numpy.ndarray
            Array of map data. This must be cropped!
        kernelSize : int, optional
            Size of kernel as the number of pixels to dilate by i.e 1
            gives a 3x3 kernel.
        bg : various, optional
            Value to fill the backgraound with. Must be same dtype as
            input array.

        Returns
        -------
        numpy.ndarray
            Map of this grains coarsened data.
        """
        grainMapData = self.grainMapData(mapData)
        grainMapDataCoarse = np.full_like(grainMapData, np.nan)

        for i, j in np.ndindex(grainMapData.shape):
            if np.isnan(grainMapData[i, j]):
                grainMapDataCoarse[i, j] = bg
            else:
                coarseValue = 0

                yLow = i - kernelSize if i - kernelSize >= 0 else 0
                yHigh = i + kernelSize + 1 if i + kernelSize + 1 <= grainMapData.shape[0] else grainMapData.shape[0]

                xLow = j - kernelSize if j - kernelSize >= 0 else 0
                xHigh = j + kernelSize + 1 if j + kernelSize + 1 <= grainMapData.shape[1] else grainMapData.shape[1]

                numPoints = 0
                for k in range(yLow, yHigh):
                    for l in range(xLow, xHigh):
                        if not np.isnan(grainMapData[k, l]):
                            coarseValue += grainMapData[k, l]
                            numPoints += 1

                grainMapDataCoarse[i, j] = coarseValue / numPoints if numPoints > 0 else np.nan

        return grainMapDataCoarse

    def plotGrainData(
        self, mapData, ax=None,
        plotColourBar=False, vmin=None, vmax=None, cmap=None, cLabel="",
        plotScaleBar=False, plotSlipTraces=False, plotSlipBands=False, **kwargs
    ):
        """
        Plot a map of this grain from the given map data.

        Parameters
        ----------
        mapData : numpy.ndarray
            Array of map data. This must be cropped!
        vmin : float, optional
            Minimum value of colour scale
        vmax : float, optional
            Minimum value of colour scale
        cLabel : str, optional
            Colour bar label text
        cmap : str, optional
            Colour map to use, default is viridis
        """
        grainMapData = self.grainMapData(mapData)

        plot = plotting.GrainPlot(self, ax=ax)
        plot.addMap(grainMapData, cmap=cmap, vmin=vmin, vmax=vmax, **kwargs)

        if plotColourBar:
            plot.addColourBar(cLabel)

        if plotScaleBar:
            plot.addScaleBar()

        if plotSlipTraces:
            plot.addSlipTraces()

        if plotSlipBands:
            plot.addSlipBands(grainMapData)

        return plot


class SlipSystem(object):
    def __init__(self, slipPlane, slipDir, crystalSym, cOverA=None):
        # Currently only for cubic
        self.crystalSym = crystalSym    # symmetry of material e.g. "cubic", "hexagonal"

        # Stored as Miller indicies (Miller-Bravais for hexagonal)
        self.slipPlaneMiller = slipPlane
        self.slipDirMiller = slipDir

        # Stored as vectors in a cartesian basis
        if crystalSym == "cubic":
            self.slipPlaneOrtho = slipPlane / np.sqrt(np.dot(slipPlane, slipPlane))
            self.slipDirOrtho = slipDir / np.sqrt(np.dot(slipDir, slipDir))
        elif crystalSym == "hexagonal":
            if cOverA is None:
                raise Exception("No c over a ratio given")
            self.cOverA = cOverA

            # Convert plane and dir from Miller-Bravais to Miller
            slipPlaneM = slipPlane[[0, 1, 3]]
            slipDirM = slipDir[[0, 1, 3]]
            slipDirM[[0, 1]] -= slipDir[2]

            # Create L matrix. Transformation from crystal to orthonormal coords
            lMatrix = SlipSystem.lMatrix(1, 1, cOverA, np.pi / 2, np.pi / 2, np.pi * 2 / 3)

            # Create Q matrix fro transforming planes
            qMatrix = SlipSystem.qMatrix(lMatrix)

            # Transform into orthonormal basis and then normalise
            self.slipPlaneOrtho = np.matmul(qMatrix, slipPlaneM)
            self.slipDirOrtho = np.matmul(lMatrix, slipDirM)
            self.slipPlaneOrtho /= np.sqrt(np.dot(self.slipPlaneOrtho, self.slipPlaneOrtho))
            self.slipDirOrtho /= np.sqrt(np.dot(self.slipDirOrtho, self.slipDirOrtho))
        else:
            raise Exception("Only cubic and hexagonal currently supported.")

    # overload ==. Two slip systems are equal if they have the same slip plane in miller
    def __eq__(self, right):
        return np.all(self.slipPlaneMiller == right.slipPlaneMiller)

    @property
    def slipPlane(self):
        return self.slipPlaneOrtho

    @property
    def slipDir(self):
        return self.slipDirOrtho

    @property
    def slipPlaneLabel(self):
        slipPlane = self.slipPlaneMiller
        if self.crystalSym == "hexagonal":
            return "({:d}{:d}{:d}{:d})".format(slipPlane[0], slipPlane[1], slipPlane[2], slipPlane[3])
        else:
            return "({:d}{:d}{:d})".format(slipPlane[0], slipPlane[1], slipPlane[2])

    @property
    def slipDirLabel(self):
        slipDir = self.slipDirMiller
        if self.crystalSym == "hexagonal":
            return "[{:d}{:d}{:d}{:d}]".format(slipDir[0], slipDir[1], slipDir[2], slipDir[3])
        else:
            return "[{:d}{:d}{:d}]".format(slipDir[0], slipDir[1], slipDir[2])

    @staticmethod
    def loadSlipSystems(filepath, crystalSym, cOverA=None):
        """Load in slip systems from file. 3 integers for slip plane normal and
           3 for slip direction. Returns a list of list of slip systems
           grouped by slip plane.

        Args:
            filepath (string): Path to file containing slip systems
            crystalSym (string): The crystal symmetry ("cubic" or "hexagonal")

        Returns:
            list(list(SlipSystem)): A list of list of slip systems grouped slip plane.

        Raises:
            IOError: Raised if not 6/8 integers per line
        """

        f = open(filepath)
        f.readline()
        colours = f.readline().strip()
        slipTraceColours = colours.split(',')
        f.close()

        if crystalSym == "hexagonal":
            vectSize = 4
        else:
            vectSize = 3

        ssData = np.loadtxt(filepath, delimiter='\t', skiprows=2, dtype=int)
        if ssData.shape[1] != 2 * vectSize:
            raise IOError("Slip system file not valid")

        # Create list of slip system objects
        slipSystems = []
        for row in ssData:
            slipSystems.append(SlipSystem(row[0:vectSize], row[vectSize:2 * vectSize], crystalSym, cOverA=cOverA))

        # Group slip sytems by slip plane
        groupedSlipSystems = SlipSystem.groupSlipSystems(slipSystems)

        return groupedSlipSystems, slipTraceColours

    @staticmethod
    def groupSlipSystems(slipSystems):
        """Groups slip systems by there slip plane.

        Args:
            slipSytems (list(SlipSystem)): A list of slip systems

        Returns:
            list(list(SlipSystem)): A list of list of slip systems grouped slip plane.
        """
        distSlipSystems = [slipSystems[0]]
        groupedSlipSystems = [[slipSystems[0]]]

        for slipSystem in slipSystems[1:]:

            for i, distSlipSystem in enumerate(distSlipSystems):
                if slipSystem == distSlipSystem:
                    groupedSlipSystems[i].append(slipSystem)
                    break
            else:
                distSlipSystems.append(slipSystem)
                groupedSlipSystems.append([slipSystem])

        return groupedSlipSystems

    @staticmethod
    def lMatrix(a, b, c, alpha, beta, gamma):
        lMatrix = np.zeros((3, 3))

        cosAlpha = np.cos(alpha)
        cosBeta = np.cos(beta)
        cosGamma = np.cos(gamma)

        sinGamma = np.sin(gamma)

        # From Randle and Engle - Intro to texture analysis
        lMatrix[0, 0] = a
        lMatrix[0, 1] = b * cosGamma
        lMatrix[0, 2] = c * cosBeta

        lMatrix[1, 1] = b * sinGamma
        lMatrix[1, 2] = c * (cosAlpha - cosBeta * cosGamma) / sinGamma

        lMatrix[2, 2] = c * np.sqrt(1 + 2 * cosAlpha * cosBeta * cosGamma -
                                    cosAlpha**2 - cosBeta**2 - cosGamma**2) / sinGamma

        # Swap 00 with 11 and 01 with 10 due to how OI orthonormalises
        # From Brad Wynne
        t1 = lMatrix[0, 0]
        t2 = lMatrix[1, 0]

        lMatrix[0, 0] = lMatrix[1, 1]
        lMatrix[1, 0] = lMatrix[0, 1]

        lMatrix[1, 1] = t1
        lMatrix[0, 1] = t2

        # Set small components to 0
        lMatrix[np.abs(lMatrix) < 1e-10] = 0

        return lMatrix

    @staticmethod
    def qMatrix(lMatrix):
        # Construct matrix of reciprocal lattice zectors to transform plane normals
        # See C. T. Young and J. L. Lytton, J. Appl. Phys., vol. 43, no. 4, pp. 1408–1417, 1972.
        a = lMatrix[:, 0]
        b = lMatrix[:, 1]
        c = lMatrix[:, 2]

        volume = abs(np.dot(a, np.cross(b, c)))
        aStar = np.cross(b, c) / volume
        bStar = np.cross(c, a) / volume
        cStar = np.cross(a, b) / volume

        qMatrix = np.stack((aStar, bStar, cStar), axis=1)

        return qMatrix
