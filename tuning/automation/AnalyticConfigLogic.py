################################################################################
# Copyright 2016-2020 Advanced Micro Devices, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell cop-
# ies of the Software, and to permit persons to whom the Software is furnished
# to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IM-
# PLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNE-
# CTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
################################################################################

import math

class ProblemDefinition :

    def __init__(self, M, N, K, dType) :
        self.M = M
        self.N = N
        self.K = K
        if dType == "d" :
            self.BPE = 8
        elif dType == "s" :
            self.BPE = 4
        else : # dType == "h"
            self.BPE = 2


class HardwareProperties :

    def __init__(self, numCUs = 120, ldsSize = 65536, l2Eff = .7, \
                numChannels = 32, readBW = 64, aluRate = 256) :

        self.numCUs = numCUs
        self.ldsSize = ldsSize
        self.l2Eff = l2Eff
        self.numChannels = numChannels
        self.readBW = readBW
        self.aluRate = aluRate # depends on data type

        self.l2BandwidthPerCU = (readBW * numChannels) // numCUs


class Thresholds : 

    def __init__(self, tile0Gran = 0.8, tile1Gran = 0.8, \
                 compMemBound = 1.0, gsuGran = 1.0, ldsMinUtilization = 0.7) :

        self.tile0Gran = tile0Gran
        self.tile1Gran = tile1Gran
        self.compMemBound = compMemBound
        self.gsuGran = gsuGran
        self.ldsMinUtilization = ldsMinUtilization


# Valid parameter options
# TODO pull this from Common.py?
macroTileSizes = [32, 64, 80, 128, 160, 192, 224, 256] #[1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 6, 12, 24, 48, 96, 192, 384, 768]
macroTileSizes.sort()

# TODO what's a good set of values for this?
globalSplitUValues = [1, 2, 4, 8, 16, 24, 32, 64, 128, 256]

# TODO what's a good set of values for this?
depthUValues = [4, 8, 16, 32, 64, 128, 256]


# Function for spreadsheet logic
def getGoodSolutionParameters(problem, hardware, thresholds) :

    def checkDepthU(gsu) :
        toReturn = []
        for depthU in depthUValues :
            ldsUsed = mm0 * depthU * problem.BPE + mm1 * depthU * problem.BPE
            ldsLoad = ldsUsed / hardware.ldsSize

            if ldsLoad <= 1 and ldsLoad > thresholds.ldsMinUtilization :
                toReturn.append((mm0, mm1, gsu, depthU))
        
        return toReturn 

    def checkGSU() :
        toReturn = []
        for gsu in globalSplitUValues :
            numTiles = math.ceil(mTiles * nTiles * gsu)

            k = math.ceil(problem.K / gsu)

            bytesPerCU = (mm0 * k * pr.BPE + mm1 * k * pr.BPE + mm0 * mm1 * pr.BPE)
            cyclesPerCU = (mm0 * mm1 * k * 2) / hw.aluRate
            roofLine = bytesPerCU / cyclesPerCU
            compMemBoundFactor = (hw.l2Eff * hw.l2BandwidthPerCU) / roofLine

            if (hardware.numCUs / numTiles) * compMemBoundFactor >= thresholds.compMemBound \
                                and (numTiles / hardware.numCUs) >= 1 :
                toReturn += checkDepthU(gsu)

        return toReturn

    toReturn = []
    for mm0 in macroTileSizes :

        mTiles = pr.M / mm0
        tile0Gran = mTiles / math.ceil(mTiles)

        if tile0Gran < thresholds.tile0Gran :
            continue

        for mm1 in macroTileSizes :

            nTiles = pr.N / mm1 
            tile1Gran = nTiles / math.ceil(nTiles)

            if tile1Gran < thresholds.tile1Gran :
                continue
            
            toReturn += checkGSU()

    return toReturn


# test call
th = Thresholds()
hw = HardwareProperties()
pr = ProblemDefinition(1000, 1000, 500, "s")

print(getGoodSolutionParameters(pr, hw, th))