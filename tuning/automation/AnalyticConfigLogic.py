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

numCUs = 120
ldsSize = 65536
l2Eff = 70
dataType = "s"
threadsPerCU = 256
numChannels = 32
readBW = 64

# TODO where do these come from? Depends on hardware? Value for "d"? Is brain float supported by Tensile?
aluRate = 256 #if dataType == "s" 256 elif dataType == "h" 1024 elif dataType == "d" 128 else 512
l2BandwidthPerCU = (readBW * numChannels) // numCUs
# TODO where does 128 come from? What does CSU stand for?
csuGran = 128 / numCUs
# TODO what is this?
BPE = 4 # stuff for other data types

tile0GranThresh = 1.0
tile1GranThresh = 1.0
compMemBoundThresh = 1.0

# TODO pull this from Common.py
macroTileSizes = [32, 64, 80, 128, 160, 192, 224, 256] #[1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 6, 12, 24, 48, 96, 192, 384, 768]
macroTileSizes.sort()

# TODO what's a good set of values for this?
globalSplitUValues = [1, 2, 4, 8, 16, 24, 32, 64]

##################################
# Values calculated in spreadsheet
##################################
M = 1024
N = 2048
K = 1600

tileSizes = macroTileSizes

# N45 matrix calculation formula
def compMemBoundFactor(mm0, mm1) :
    magic = 1 # TODO in spreadsheet this is an empty cell (0): is this correct? (I think no)
    return ( (l2Eff / 100) * l2BandwidthPerCU ) / ( (mm0 * K * BPE + mm1 * K * BPE + mm0 * mm1 * magic) / (mm0 * mm1 * K * 2 / aluRate) )

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
goodMacroTiles = []
for i in range(0, len(tileSizes)):
    for j in range(0, len(tileSizes)):

        mm0 = tileSizes[i]
        mm1 = tileSizes[j]
        numMTiles = mTiles[i]
        numNTiles = nTiles[j]

        numTiles = math.ceil(numMTiles * numNTiles)
        compMemFact = compMemBoundFactor(mm0, mm1)

        if (numCUs / numTiles) * compMemFact >= compMemBoundThresh and (numTiles / numCUs) >= 1 :
            goodMacroTiles.append((mm0, mm1))



# print(tile0Grans)
# print("*************************")
# print(mTiles)
# print("*************************")
# print(mTilesXtile0Grans)
