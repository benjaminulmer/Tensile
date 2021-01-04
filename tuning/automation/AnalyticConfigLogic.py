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
        else : # dType == "h" or "b"
            self.BPE = 2


class HardwareProperties :

    def __init__(self, dType, numCUs = 60, ldsSize = 65536, l2Eff = .7, \
                numChannels = 32, readBW = 64) :

        self.numCUs = numCUs
        self.ldsSize = ldsSize
        self.l2Eff = l2Eff
        self.numChannels = numChannels
        self.readBW = readBW

        if dType == "d" :
            self.aluRate = 128 # don't know what correct value is
        elif dType == "s" :
            self.aluRate = 256
        elif dType == "h" :
            self.aluRate = 1024
        else : # dType == "b"
            self.aluRate = 512

        self.l2BandwidthPerCU = (readBW * numChannels) // numCUs


class Thresholds : 

    def __init__(self, tile0Gran = 0.8, tile1Gran = 0.8, \
                 compMemBound = 1.0, gsuGran = 1.0, ldsMinUtilization = 0.7) :

        self.tile0Gran = tile0Gran
        self.tile1Gran = tile1Gran
        self.compMemBound = compMemBound
        self.gsuGran = gsuGran # not used currently
        self.ldsMinUtilization = ldsMinUtilization


# Valid parameter options
# TODO pull this from Common.py?
macroTileSizes = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 6, 12, 24, 48, 96, 192, 384, 768]
macroTileSizes.sort()

# TODO what's a good set of values for this?
globalSplitUValues = [1, 2, 4, 8, 16, 24, 32, 64, 128, 256]

# TODO what's a good set of values for this?
depthUValues = [4, 8, 16, 32, 64, 128, 256]

# TODO are these good values?
defaultWorkGroups = [[16, 16, 1], [8, 16, 2], [16, 8, 2], [16, 4, 4], [4, 16, 4], [8, 8, 4], [32, 16, 1], [16, 32, 1], [64, 16, 1], [16, 64, 1]]


# Returns "good" solution parameters for problem given hardware properties and user provided thresholds
# Based on Raman's spreadsheet tuning logic
def getGoodSolutionParameters(problem, hardware, thresholds) :

    def checkDepthU(gsu) :
        toReturn = []
        for depthU in depthUValues :
            ldsUsed = mm0 * depthU * problem.BPE + mm1 * depthU * problem.BPE
            ldsUsedRound = int(2**(math.ceil(math.log(ldsUsed, 2)))) # round up to nearest power of 2
            ldsUsed += ldsUsedRound
            ldsLoad = ldsUsed / hardware.ldsSize

            if ldsLoad <= 1 and ldsLoad > thresholds.ldsMinUtilization :
                toReturn.append({"mm0":mm0, "mm1":mm1, "gsu":gsu, "depthU":depthU})
        
        return toReturn 

    def checkGSU() :
        toReturn = []
        for gsu in globalSplitUValues :
            numTiles = math.ceil(mTiles * nTiles * gsu)

            k = math.ceil(problem.K / gsu)

            bytesPerCU = (mm0 * k * problem.BPE + mm1 * k * problem.BPE + mm0 * mm1 * problem.BPE)
            cyclesPerCU = (mm0 * mm1 * k * 2) / hardware.aluRate
            roofLine = bytesPerCU / cyclesPerCU
            compMemBoundFactor = (hardware.l2Eff * hardware.l2BandwidthPerCU) / roofLine


            # TODO best logic for here
            if (hardware.numCUs / numTiles) * compMemBoundFactor >= thresholds.compMemBound \
                                and (numTiles / hardware.numCUs) >= 1 :

            #if (compMemBoundFactor >= 1.0 and compMemBoundFactor <= 2.0) :
                toReturn += checkDepthU(gsu)

        return toReturn

    toReturn = []
    for mm0 in macroTileSizes :

        mTiles = problem.M / mm0
        tile0Gran = mTiles / math.ceil(mTiles)

        if tile0Gran < thresholds.tile0Gran :
            continue

        for mm1 in macroTileSizes :

            nTiles = problem.N / mm1
            tile1Gran = nTiles / math.ceil(nTiles)

            if tile1Gran < thresholds.tile1Gran :
                continue
            
            toReturn += checkGSU()

    return toReturn

# Returns possible tt values for given mm and wg
def getThreadTiles(mm0, mm1, workGroupSizes) :
    tt = []

    for wg in workGroupSizes :
        tt0 = mm0 // wg[0]
        tt1 = mm1 // wg[1]

        tt.append((tt0, tt1))

    return tt


# testing stuff
if __name__ == "__main__" :

    th = Thresholds()
    wgs = [[16, 16, 1], [8, 16, 2], [16, 8, 2], [16, 4, 4], [4, 16, 4], [8, 8, 4]]
    results = {}
    total = 0

    # for d in ["s", "h", "b", "d"] :
    #     for m in range(100, 10000, 200) :
    #         for n in range(m, 10000, 200) :
    #             for k in range(100, 10000, 200) :

    #                 hw = HardwareProperties(d)
    #                 pr = ProblemDefinition(m, n, k, d)
    #                 num = len(getGoodSolutionParameters(pr, hw, th))

    #                 #if num == 0 :
    #                 #    print((m, n, k, d))

    #                 if num in results :
    #                     results[num] += 1
    #                 else :
    #                     results[num] = 1
    #                 total += 1

    pr = ProblemDefinition(3072, 4096, 1024, 's')
    hw = HardwareProperties('s')
    foo = getGoodSolutionParameters(pr, hw, th)
    for f in foo :
        print(f)

    #pr = ProblemDefinition(100, 300, 800, dt)
    # print(getGoodSolutionParameters(pr, hw, th))

    # threadTileSizes = getThreadTiles(128, 64, workGroupSizes)

    # for (tt, wg) in zip(threadTileSizes, workGroupSizes) :
    #     print(tt, end=" : ")
    #     print(wg, end=" : ")
    #     print((tt[0] * wg[0], tt[1] * wg[1]))
