###############################################################################
# Copyright 2016-2021 Advanced Micro Devices, Inc. All rights reserved.
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

from . import BenchmarkProblems
from . import ClientExecutable
from . import ClientWriter
from . import LibraryIO
from . import LibraryLogic
from . import Common
from .Common import globalParameters, print1, printWarning, ensurePath, assignGlobalParameters, \
                    pushWorkingPath, popWorkingPath, restoreDefaultGlobalParameters, HR
from .Tensile import addCommonArguments, argUpdatedGlobalParameters
from .SolutionStructs import ProblemSizes
from . import __version__

import argparse
import copy
import os
import shutil
import sys

def TensileTuneRepair(userArgs):

    # argument parsing and related setup
    argParser = argparse.ArgumentParser()
    argParser.add_argument("ConfigFile",
                           help="Tuning config file used in tuning")
    argParser.add_argument("OutputPath",
                           help="Where to run benchmarks and output results")

    addCommonArguments(argParser)
    args = argParser.parse_args(userArgs)

    ##############################################
    # Retuning
    ##############################################
    outPath = ensurePath(os.path.abspath(args.OutputPath))
    restoreDefaultGlobalParameters()
    assignGlobalParameters({"LibraryFormat": "msgpack",
                            "OutputPath": outPath,
                            "WorkingPath": outPath})

    overrideParameters = argUpdatedGlobalParameters(args)
    for key, value in overrideParameters.items():
        print1("Overriding {0}={1}".format(key, value))
        Common.globalParameters[key] = value

    rawYaml = LibraryIO.readYAML(args.ConfigFile)
    ll = rawYaml["LibraryLogic"]

    # write library logic file
    LibraryLogic.main({"ScheduleName":      ll["ScheduleName"],
                        "ArchitectureName": ll["ArchitectureName"],
                        "DeviceNames":      ll["DeviceNames"] } )


def main():
    TensileTuneRepair(sys.argv[1:])
