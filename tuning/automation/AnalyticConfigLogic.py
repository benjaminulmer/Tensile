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

# Problem definition
M = 1000
N = 1000
K = 500
dataType = "s"
BPE = 4 # bytes per element (from dataType)

# Hardware properties
numCUs = 120
ldsSize = 65536
l2Eff = 70

threadsPerCU = 256
numChannels = 32
readBW = 64

aluRate = 256 # arithmetic-logic-unit rate: ops / CU / cycle # TODO set from data type and hardware
l2BandwidthPerCU = (readBW * numChannels) // numCUs

# Thresholds and tolerances 
tile0GranThresh = 1.0
tile1GranThresh = 1.0
compMemBoundThresh = 1.0
gsuGran = 128 / numCUs # TODO where does 128 come from? Is this GlobalSplitU granularity?

# Options for splitting problem into workgroups
# TODO pull this from Common.py?
macroTileSizes = [32, 64, 80, 128, 160, 192, 224, 256] #[1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 6, 12, 24, 48, 96, 192, 384, 768]
macroTileSizes.sort()

# TODO what's a good set of values for this?
globalSplitUValues = [1, 2, 4, 8, 16, 24, 32, 64, 128, 256]

# TODO what's a good set of values for this?
depthUValues = [4, 8, 16, 32, 64, 128, 256]

##################################
# Values calculated in spreadsheet
##################################
tileSizes = macroTileSizes

# N45 matrix calculation formulas
def bytesPerCU(mm0, mm1, k) :
    # bytes from A + bytes from B + bytes from C
    return (mm0 * k * BPE + mm1 * k * BPE + mm0 * mm1 * BPE)

def cyclesPerCU(mm0, mm1, k) :
    return (mm0 * mm1 * k * 2) / aluRate

def roofLine(mm0, mm1, k) :
    return bytesPerCU(mm0, mm1, k) / cyclesPerCU(mm0, mm1, k)

# bytes we can deliver / bytes we need
def compMemBoundFactor(mm0, mm1, k) :
    return ( (l2Eff / 100) * l2BandwidthPerCU ) / roofLine(mm0, mm1, k)
##################################

# C37 and D37
mTiles = [M / size for size in tileSizes]
nTiles = [N / size for size in tileSizes]

# C39 and C40
tile0Grans = [tiles / math.ceil(tiles) for tiles in mTiles]
tile1Grans = [tiles / math.ceil(tiles) for tiles in nTiles]

# C42 and N35
mTileGranU = []
mTilesXtile0Grans = []
for i in range(0, len(mTiles)) :
    mTileGranU.append(False if mTiles[i] * tile0Grans[i] < tile0GranThresh else True)
    # N35 - adapting logic
    # seems to be numTiles if gran = 1 and 0 otherwise
    mTilesXtile0Grans.append(mTiles[i] if tile0Grans[i] == 1.0 else 0)

# C43 and O35
nTileGranU = []
nTilesXtile1Grans = []
for i in range(0, len(nTiles)) :
    nTileGranU.append(False if nTiles[i] * tile1Grans[i] < tile1GranThresh else True)
    # O35 - adapting logic
    # seems to be numTiles if gran = 1 and 0 otherwise
    nTilesXtile1Grans.append(nTiles[i] if tile1Grans[i] == 1.0 else 0)

# C55
goodMTandGSU = []
totals = []
for gsu in globalSplitUValues :
    for mm0, numMTiles in zip(tileSizes, mTiles) :
        for mm1, numNTiles in zip(tileSizes, nTiles):

            numTiles = math.ceil(numMTiles * numNTiles * gsu)
            compMemFact = compMemBoundFactor(mm0, mm1, math.ceil(K / gsu))

            if (numCUs / numTiles) * compMemFact >= compMemBoundThresh and (numTiles / numCUs) >= 1 :
                goodMTandGSU.append((mm0, mm1, gsu))
                totals.append(numMTiles * numNTiles * gsu)

goodAll = []
for (mm0, mm1, gsu) in goodMTandGSU :
    for depthU in depthUValues :
        ldsUsed = mm0 * depthU * BPE + mm1 * depthU * BPE
        ldsLoad = ldsUsed / ldsSize

        if ldsLoad <= 1 and ldsLoad > 0.7 :
            goodAll.append((mm0, mm1, gsu, depthU))
        
print(goodAll)

# print(goodMTandGSU)
# print("*******************************")
# print(totals)

# print(min(totals))
# print(max(totals))

# print(tile0Grans)
# print("*************************")
# print(mTiles)
# print("*************************")
# print(mTilesXtile0Grans)
