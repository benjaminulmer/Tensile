#!/bin/sh

HELP_STR="
Usage: ./analyze-results.sh -o OUTPUT_PATH -s SIZE -f FREQ -z LOG_FILE -r REF_PATH -b BENCH_PATH [options]

Options:
  [-h|--help]                 Display this help message
  [-o|--output PATH]          Output path
  [-s|--size]                 Data size
  [-f|--freq]                 Clock rate
  [-z|--size-log]             Log file of sizes
  [-r|--reference-path PATH]  Path to reference library
  [-b|--benchmark-path PATH]  Path to benchmark libraru
  [-g|--gpu]                  GPU
  [-m|--mfma]                 Was MFMA enabled
  [-c|--count]                ??
  [-n|--no-plot]              Skip plotting
"
HELP=false
PLOT=true
MFMA=false
COUNT=false

OPTS=`getopt -o hf:s:b:o:r:z:g:mcn \
--long help,freq:,size-log:,size:,output-path:,reference-path:,benchmark-path:,\
gpu:,mfma,count,no-plot -n 'parse-options' -- "$@"`

if [ $? != 0 ] ; then echo "Failed parsing options." >&2 ; exit 1 ; fi

eval set -- "$OPTS"

while true; do
  case "$1" in
    -h | --help )              HELP=true; shift ;;
    -r | --reference-path )    REFERENCE_PATH="$2"; shift 2;;
    -b | --benchmark-path  )   BENCHMARK_PATH="$2"; shift 2;;
    -o | --output-path )       OUTPUT_PATH="$2"; shift 2;;
    -z | --size-log)           LOG="$2"; shift 2;;
    -f | --freq)               FREQ="$2"; shift 2;;
    -s | --size)               SZ="$2"; shift 2;;
    -g | --gpu ) 	             GPU="$2"; shift 2;;
    -m | --mfma )	             MFMA=true; shift ;;
    -c | --count )	           COUNT=true; shift ;;
    -n | --no-plot )           PLOT=false; shift ;;
    -- ) shift; break ;;
    * ) break ;;
  esac
done

if $HELP; then
  echo "${HELP_STR}" >&2
  exit 2
fi

if [ -z ${REFERENCE_PATH+foo} ]; then
  printf "Need a reference results path\n"
  exit 2
fi

if [ -z ${BENCHMARK_PATH+foo} ]; then
  printf "Need the benchmark results path\n"
  exit 2
fi

if [ -z ${OUTPUT_PATH+foo} ]; then
  printf "Need the output path\n"
  exit 2
fi

if [ -z ${LOG+foo} ]; then
  printf "Need to select a log file\n"
  exit 2
fi

if [ -z ${FREQ+foo} ]; then
  printf "Need clock rate\n"
  exit 2
fi

if [ -z ${SZ+foo} ]; then
  printf "Need data size\n"
  exit 2
fi

if [ -z ${GPU+foo} ]; then
  printf "GPU not specified, assuming MI60\n"
  GPU=vega20
fi

CASE_REFERENCE=${OUTPUT_PATH}/reference
CASE_NEW=${OUTPUT_PATH}/new
CASE_FINAL=${OUTPUT_PATH}/final

mkdir -p ${CASE_REFERENCE}
mkdir -p ${CASE_NEW}
mkdir -p ${CASE_FINAL}

REFERENCE_RESULTS=${CASE_REFERENCE}/results
REFERENCE_AGGREGATED=${CASE_REFERENCE}/aggregated
NEW_RESULTS=${CASE_NEW}/results
NEW_AGGREGATED=${CASE_NEW}/aggregated

mkdir -p ${REFERENCE_RESULTS}
mkdir -p ${REFERENCE_AGGREGATED}
mkdir -p ${NEW_RESULTS}
mkdir -p ${NEW_AGGREGATED}

cp ${REFERENCE_PATH}/* ${REFERENCE_RESULTS}
cp ${BENCHMARK_PATH}/* ${NEW_RESULTS}

#determing full path of tools root
TOOLS_ROOT=`dirname "$0"`
TOOLS_ROOT=`( cd "${TOOLS_ROOT}" && cd .. && pwd )`
AUTOMATION_ROOT="${TOOLS_ROOT}/automation"

ANALYSIS=${AUTOMATION_ROOT}/PerformanceAnalysis.py
COMPARE=${AUTOMATION_ROOT}/CompareResults.py
PLOT_DIFF=${AUTOMATION_ROOT}/PlotDifference.py
PLOT_RESULTS=${AUTOMATION_ROOT}/PlotResults.py


python3 ${ANALYSIS} ${REFERENCE_RESULTS} ${REFERENCE_AGGREGATED} ${FREQ} ${SZ} ${LOG} ${GPU} ${MFMA} ${COUNT}
python3 ${ANALYSIS} ${NEW_RESULTS} ${NEW_AGGREGATED} ${FREQ} ${SZ} ${LOG} ${GPU} ${MFMA} ${COUNT}

ls ${NEW_AGGREGATED}/*aggregated* | xargs -n1 basename | xargs -I{} python3 ${COMPARE} ${REFERENCE_AGGREGATED}/{} ${NEW_AGGREGATED}/{} ${CASE_FINAL}/{}

if $PLOT; then

  REFERENCE_PLOT=${CASE_REFERENCE}/plot
  NEW_PLOT=${CASE_NEW}/plot

  mkdir -p ${REFERENCE_PLOT}
  mkdir -p ${NEW_PLOT}

  aggregated_files=$(ls ${REFERENCE_AGGREGATED}/*aggregated*)
  for file in ${aggregated_files}; do
    filename=$(basename "$file")
    namepart="${filename%-aggregated.*}"

    python3 ${PLOT_RESULTS} ${file} ${REFERENCE_PLOT}/${namepart}
  done

  aggregated_files=$(ls ${NEW_AGGREGATED}/*aggregated*)
  for file in ${aggregated_files}; do
    filename=$(basename "$file")
    namepart="${filename%-aggregated.*}"

    python3 ${PLOT_RESULTS} ${file} ${NEW_PLOT}/${namepart}
  done

fi
