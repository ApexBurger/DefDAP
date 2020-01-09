# Copyright 2019 Mechanics of Microstructures Group
#    at The University of Manchester
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import pathlib
from typing import Union

import numpy as np
import pandas as pd


class EBSDDataLoader:

    def __init__(self):
        self.loadedMetadata = {
            'xDim': 0,
            'yDim': 0,
            'stepSize': 0.,
            'numPhases': 0,
            'phaseNames': []
        }
        self.loadedData = {
            'eulerAngle': None,
            'bandContrast': None,
            'phase': None
        }

    def checkMetadata(self):
        if len(self.loadedMetadata['phaseNames']) != self.loadedMetadata['numPhases']:
            print("Number of phases mismatch.")
            raise AssertionError

    def loadOxfordCPR(self, fileStub: pathlib.Path):
        """ A .cpr file is a metadata file describing EBSD data.
        This function opens the cpr file, reading in the x and y
        dimensions and phase names."""
        filePath = fileStub.with_suffix(".cpr")
        if not filePath.is_file():
            raise FileNotFoundError("Cannot open file {}".format(filePath))

        cprFile = open(str(filePath), 'r')

        for line in cprFile:
            if 'xCells' in line:
                self.loadedMetadata['xDim'] = int(line.split("=")[-1])
            elif 'yCells' in line:
                self.loadedMetadata['yDim'] = int(line.split("=")[-1])
            elif 'GridDistX' in line:
                self.loadedMetadata['stepSize'] = float(line.split("=")[-1])
            elif '[Phases]' in line:
                self.loadedMetadata['numPhases'] = int(next(cprFile).split("=")[-1])
            elif '[Phase' in line:
                phaseName = next(cprFile).split("=")[-1].strip('\n')
                self.loadedMetadata['phaseNames'].append(phaseName)

        cprFile.close()

        self.checkMetadata()

        return self.loadedMetadata

    def loadOxfordCRC(self, fileStub: pathlib.Path):
        """Read binary EBSD data from a .crc file"""
        xDim = self.loadedMetadata['xDim']
        yDim = self.loadedMetadata['yDim']

        filePath = fileStub.with_suffix(".crc")

        if not filePath.is_file():
            raise FileNotFoundError("Cannot open file {}".format(filePath))

        dataFormat = np.dtype([
            ('Phase', 'b'),
            ('Eulers', [('ph1', 'f'), ('phi', 'f'), ('ph2', 'f')]),
            ('MAD', 'f'),
            ('BC', 'uint8'),
            ('IB3', 'uint8'),
            ('IB4', 'uint8'),
            ('IB5', 'uint8'),
            ('IB6', 'f')
        ])
        binData = np.fromfile(str(filePath), dataFormat, count=-1)

        self.loadedData['bandContrast'] = np.reshape(
            binData['BC'], (yDim, xDim)
        )
        self.loadedData['phase'] = np.reshape(
            binData['Phase'], (yDim, xDim)
        )
        eulerAngles = np.reshape(
            binData['Eulers'], (yDim, xDim)
        )
        # flatten the structures so that the Euler angles are stored
        # into a normal array
        eulerAngles = np.array(eulerAngles.tolist()).transpose((2, 0, 1))
        self.loadedData['eulerAngle'] = eulerAngles

        return self.loadedData

    def loadOxfordCTF(self, filePath: pathlib.Path):
        """ A .ctf file is a HKL single orientation file. This is a
        data file generated by the Oxford EBSD instrument."""

        # open data file and read in metadata
        if not filePath.is_file():
            raise FileNotFoundError("Cannot open file {}".format(filePath))

        ctfFile = open(str(filePath), 'r')

        for i, line in enumerate(ctfFile):
            if 'XCells' in line:
                xDim = int(line.split()[-1])
                self.loadedMetadata['xDim'] = xDim
            elif 'YCells' in line:
                yDim = int(line.split()[-1])
                self.loadedMetadata['yDim'] = yDim
            elif 'XStep' in line:
                self.loadedMetadata['stepSize'] = float(line.split()[-1])
            elif 'Phases' in line:
                numPhases = int(line.split()[-1])
                self.loadedMetadata['numPhases'] = numPhases
                for j in range(numPhases):
                    self.loadedMetadata['phaseNames'].append(
                        next(ctfFile).split()[2]
                    )
                numHeaderLines = i + j + 3
                # phases are last in the header so break out the loop
                break

        ctfFile.close()

        self.checkMetadata()

        # now read the data from file
        dataFormat = np.dtype([
            ('Phase', 'b'),
            ('Eulers', [('ph1', 'f'), ('phi', 'f'), ('ph2', 'f')]),
            ('MAD', 'f'),
            ('BC', 'uint8')
        ])
        binData = np.loadtxt(
            str(filePath), dataFormat, delimiter='\t',
            skiprows=numHeaderLines, usecols=(0, 5, 6, 7, 8, 9)
        )

        self.loadedData['bandContrast'] = np.reshape(
            binData['BC'], (yDim, xDim)
        )
        self.loadedData['phase'] = np.reshape(
            binData['Phase'], (yDim, xDim)
        )
        eulerAngles = np.reshape(
            binData['Eulers'], (yDim, xDim)
        )
        # flatten the structures the Euler angles are stored into a
        # normal array
        eulerAngles = np.array(eulerAngles.tolist()).transpose((2, 0, 1))
        self.loadedData['eulerAngle'] = eulerAngles * np.pi / 180.

        return self.loadedMetadata, self.loadedData


class DICDataLoader:

    def __init__(self):
        self.loadedMetadata = {
            'format': "",
            'version': "",
            'binning': "",
            'xDim': 0,
            'yDim': 0
        }
        self.loadedData = {
            'xc': None,
            'yc': None,
            'xd': None,
            'yd': None
        }

    def checkData(self):
        # Calculate size of map from loaded data and check it matches
        # values from metadata
        coords = self.loadedData['xc']
        xdim = int(
            (coords.max() - coords.min()) / min(abs(np.diff(coords))) + 1
        )

        coords = self.loadedData['yc']
        ydim = int(
            (coords.max() - coords.min()) / max(abs(np.diff(coords))) + 1
        )

        assert xdim == self.loadedMetadata['xDim'], "Dimensions of data and header do not match"
        assert ydim == self.loadedMetadata['yDim'], "Dimensions of data and header do not match"

    def loadDavisMetadata(self, fileName, fileDir=""):
        # Load metadata
        filePath = pathlib.Path(fileDir) / pathlib.Path(fileName)
        if not filePath.is_file():
            raise FileNotFoundError("Cannot open file {}".format(filePath))

        with open(str(filePath), 'r') as f:
            header = f.readline()
        metadata = header.split()

        # Software name and version
        self.loadedMetadata['format'] = metadata[0].strip('#')
        self.loadedMetadata['version'] = metadata[1]
        # Sub-window width in pixels
        self.loadedMetadata['binning'] = int(metadata[3])
        # size of map along x and y (from header)
        self.loadedMetadata['xDim'] = int(metadata[5])
        self.loadedMetadata['yDim'] = int(metadata[4])

        return self.loadedMetadata

    def loadDavisData(self, fileName, fileDir=""):
        filePath = pathlib.Path(fileDir) / pathlib.Path(fileName)
        if not filePath.is_file():
            raise FileNotFoundError("Cannot open file {}".format(filePath))

        data = pd.read_table(str(filePath), delimiter='\t', skiprows=1, header=None)
        # x and y coordinates
        self.loadedData['xc'] = data.values[:, 0]
        self.loadedData['yc'] = data.values[:, 1]
        # x and y displacement
        self.loadedData['xd'] = data.values[:, 2]
        self.loadedData['yd'] = data.values[:, 3]

        self.checkData()

        return self.loadedData


def loadEBSDData(file_path: Union[str, os.PathLike]) -> EBSDDataLoader:
    data_loader = EBSDDataLoader()

    path = pathlib.Path(file_path)

    if path.suffix == ".ctf":
        data_loader.loadOxfordCTF(path)
    elif path.suffix == ".cpr" or ".crc":
        file_stub = path.with_suffix('')
        data_loader.loadOxfordCPR(file_stub)
        data_loader.loadOxfordCRC(file_stub)
    return data_loader