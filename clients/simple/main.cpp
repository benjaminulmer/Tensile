#include <cstdio>
#include <random>
#ifdef WIN32
#include "Windows.h"
#else
#include <time.h>
#endif

#define VALIDATE 0
#define SWITCH_AB 0


#if Cobalt_BACKEND_HIP
/*******************************************************************************
 * HIP stuff
 ******************************************************************************/
#include <hip_runtime.h>
#include "kernel_hip.h"

hipError_t status;
#define CHECK(STATUS) \
  { \
    hipError_t tmp_status = STATUS;
    if (tmp_status != hipSuccess) { \
      fprintf(stderr, "error: '%s' (%d) at %s:%d\n", hipGetErrorString(tmp_status), tmp_status, __FILE__, __LINE__); \
    } \
  }

#else
/*******************************************************************************
 * OpenCL stuff
 ******************************************************************************/
#include <CL/cl.h>
#include "kernel_opencl.h"

class Timer {
public:
  Timer::Timer() {
#ifdef WIN32
    QueryPerformanceFrequency( &frequency );
#else
    // nothing
#endif
  }

  void Timer::start() {
#ifdef WIN32
    QueryPerformanceCounter( &startTime );
#else
    clock_gettime( CLOCK_REALTIME, &startTime );
#endif
  }

  // returns elapsed time in seconds
  double Timer::elapsed_sec() {
    return elapsed_us() / 1000000.0;
  }
  // returns elapsed time in seconds
  double Timer::elapsed_ms() {
    return elapsed_us() / 1000.0;
  }
  double Timer::elapsed_us() {
    double elapsed_us;
#ifdef WIN32
    LARGE_INTEGER currentTime;
    QueryPerformanceCounter( &currentTime );
    elapsed_us = double(currentTime.QuadPart-startTime.QuadPart)/(frequency.QuadPart/1000000.0);
#else
    timespec currentTime;
    clock_gettime( CLOCK_REALTIME, &currentTime);
    elapsed_us = (currentTime.tv_sec - startTime.tv_sec)*1000000.0
      + (currentTime.tv_nsec - startTime.tv_nsec)/1000.0;
#endif
    return elapsed_us;
  }


private:
#ifdef WIN32
  LARGE_INTEGER startTime;
  LARGE_INTEGER frequency; 
#else
  timespec startTime;
#endif
};

void sgemm_NT(
  bool transA, bool transB,
  float  *C, float  *A, float  *B,
  float const alpha, float const beta,
  unsigned int const ldc, unsigned int const lda, unsigned int const ldb,
  unsigned int const M, unsigned int const N, unsigned int const K );

cl_int status;
#define CHECK(STATUS) \
  do { \
    cl_int tmp_status = STATUS; \
    if (tmp_status != CL_SUCCESS) { \
      fprintf(stderr, "error: (%d) at %s:%d\n", tmp_status, __FILE__, __LINE__); \
    } \
  } while(false);

void makeKernel(
    cl_kernel *kernel,
    cl_command_queue queue,
    const char *kernelSource,
    const char *sourceBuildOptions);

#endif

// these need to agree with kernel
#define DATA_TYPE_STR_A     float
#define DATA_TYPE_STR_B     float
#define DATA_TYPE_STR_C     float
#define DATA_TYPE_STR_ALPHA float
#define DATA_TYPE_STR_BETA  float
#define WG_DIM_0I           16
#define WG_DIM_1J           16
#define MICRO_TILE_0I       6
#define MICRO_TILE_1J       6
#define MACRO_TILE_0I       (WG_DIM_0I*MICRO_TILE_0I)
#define MACRO_TILE_1J       (WG_DIM_1J*MICRO_TILE_1J)
#if VALIDATE
const unsigned int M = 4*96;
const unsigned int N = 3*96;
const unsigned int K = 2*96;
#else
const unsigned int M = 5760;
const unsigned int N = 5760;
const unsigned int K = 5760;
#endif
const unsigned int numEnqueues = 1;
DATA_TYPE_STR_ALPHA alpha = 1;
DATA_TYPE_STR_BETA  beta  = 0;
const unsigned int transA = 1;
const unsigned int transB = 0;

/*******************************************************************************
 * main
 ******************************************************************************/
int main( int argc, char *argv[] ) {

  // init runtime
#if Cobalt_BACKEND_OPENCL12
  printf("allocating opencl queue\n");
  cl_platform_id platform;
  cl_device_id device;
  cl_context_properties props[3] = { CL_CONTEXT_PLATFORM, 0, 0 };
  cl_context context;
  cl_command_queue queue;
  status = clGetPlatformIDs(1, &platform, nullptr); CHECK(status);
  status = clGetDeviceIDs(platform, CL_DEVICE_TYPE_GPU, 1, &device, nullptr); CHECK(status);
  props[1] = (cl_context_properties)platform;
  context = clCreateContext(props, 1, &device, NULL, NULL, &status); CHECK(status);
  queue = clCreateCommandQueue(context, device, CL_QUEUE_PROFILING_ENABLE, &status); CHECK(status);

  // compile kernel
  printf("compiling opencl kernel\n");
  const char *buildOptions = "-cl-std=CL2.0";
  const char *kernelSource;
  if ( !transA && !transB ) {
    kernelSource = kernelSource_NN;
  } else if ( !transA && transB ) {
    kernelSource = kernelSource_NT;
  } else if ( transA && !transB ) {
    kernelSource = kernelSource_TN;
  } else if ( transA && transB ) {
    kernelSource = kernelSource_TT;
  }
  cl_kernel kernel_opencl;
  makeKernel(
      &kernel_opencl,
      queue,
      kernelSource,
      buildOptions);
#endif


  // GEMM parameters
  // col-major means dim0=col, dim1=row
  // size0C = size of C column = C num rows
  const unsigned int size0C = M;
  const unsigned int size1C = N;
  const unsigned int size0A = transA ? K : M;
  const unsigned int size1A = transA ? M : K;
  const unsigned int size0B = transB ? N : K;
  const unsigned int size1B = transB ? K : N;

  // matrix sizes
  const size_t numElementsC = size0C*size1C;
  const size_t numElementsA = size0A*size1A;
  const size_t numElementsB = size0B*size1B;
  const size_t sizeC = numElementsC * sizeof(DATA_TYPE_STR_C);
  const size_t sizeA = numElementsA * sizeof(DATA_TYPE_STR_A);
  const size_t sizeB = numElementsB * sizeof(DATA_TYPE_STR_B);

  // allocate host buffers
  printf("allocating host buffers\n");
  DATA_TYPE_STR_C *hC = new DATA_TYPE_STR_C[numElementsC];
  DATA_TYPE_STR_C *hC_ref = new DATA_TYPE_STR_C[numElementsC];
  DATA_TYPE_STR_A *hA = new DATA_TYPE_STR_A[numElementsA];
  DATA_TYPE_STR_B *hB = new DATA_TYPE_STR_B[numElementsB];

  // init host buffers
  printf("initializing host buffers\n");
#if VALIDATE
  for (unsigned int i = 0; i < numElementsC; i++) {
    hC[i] = rand()%101;
    hC_ref[i] = hC[i];
  }
  for (unsigned int i = 0; i < numElementsA; i++) {
    hA[i] = rand()%101;
  }
  for (unsigned int i = 0; i < numElementsB; i++) {
    hB[i] = rand()%101;
  }
#else
  for (unsigned int i = 0; i < numElementsC; i++) { hC[i] = 1; }
  for (unsigned int i = 0; i < numElementsA; i++) { hA[i] = 1; }
  for (unsigned int i = 0; i < numElementsB; i++) { hB[i] = 1; }
#endif

  // allocate device buffers
  printf("allocating device buffers\n");
#if Cobalt_BACKEND_HIP
  DATA_TYPE_STR_C *dC;
  DATA_TYPE_STR_A *dA;
  DATA_TYPE_STR_B *dB;
  status = hipMalloc( &dC, sizeC); CHECK(status);
  status = hipMalloc( &dA, sizeA); CHECK(status);
  status = hipMalloc( &dB, sizeB); CHECK(status);
  status = hipMemcpy( dC, hC, sizeC, hipMemcpyHostToDevice ); CHECK(status);
  status = hipMemcpy( dA, hA, sizeA, hipMemcpyHostToDevice ); CHECK(status);
  status = hipMemcpy( dB, hB, sizeB, hipMemcpyHostToDevice ); CHECK(status);
#else
  cl_mem dC = clCreateBuffer( context, CL_MEM_READ_WRITE, sizeC, nullptr, &status); CHECK(status);
  cl_mem dA = clCreateBuffer( context, CL_MEM_READ_ONLY , sizeA, nullptr, &status); CHECK(status);
  cl_mem dB = clCreateBuffer( context, CL_MEM_READ_ONLY , sizeB, nullptr, &status); CHECK(status);
  clEnqueueWriteBuffer(queue, dC, CL_TRUE, 0, sizeC, hC, 0, nullptr, nullptr );
  clEnqueueWriteBuffer(queue, dA, CL_TRUE, 0, sizeA, hA, 0, nullptr, nullptr );
  clEnqueueWriteBuffer(queue, dB, CL_TRUE, 0, sizeB, hB, 0, nullptr, nullptr );
#endif
  
  // init device buffers
  printf("initializing device buffers\n");

  // dim
#if Cobalt_BACKEND_HIP
  dim3 workGroup( WG_DIM_0I, WG_DIM_1J, 1 );
  dim3 blocks(size0C/MACRO_TILE_0I, size1C/MACRO_TILE_1J, 1);  
#else
  size_t localSize[3] = { WG_DIM_0I, WG_DIM_1J, 1 };
  size_t globalSize[3] = { ((size0C+MACRO_TILE_0I-1)/MACRO_TILE_0I)*WG_DIM_0I, ((size1C+MACRO_TILE_1J-1)/MACRO_TILE_1J)*WG_DIM_1J, 1 };  
#endif

  // enqueue kernel
#if Cobalt_BACKEND_HIP
  printf("enqueueing hip kernel block=%ux%u, work-group=%ux%u\n",blocks.x, blocks.y, workGroup.x, workGroup.y);
  hipLaunchKernel(
      HIP_KERNEL_NAME(kernel_hip),
      blocks,
      workGroup,
      0, // groupMemBytes
      nullptr, // stream
      dC,
      dA,
      dB,
      alpha,
      beta,
      0, // offset C
      0, // offset A
      0, // offset B
      size0C, // stride1C,
      size0A, // stride1A,
      size0B, // stride1B,
      M,
      N,
      K );
#else
  printf("enqueueing opencl kernel global=%llux%llu, local=%llux%llu\n", globalSize[0], globalSize[1], localSize[0], localSize[1]);
  cl_uint argIdx = 0;
  CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(cl_mem), &dC ); )
#if SWITCH_AB
  CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(cl_mem), &dB ); )
  CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(cl_mem), &dA ); )
#else
    CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(cl_mem), &dA ); )
    CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(cl_mem), &dB ); )
#endif
  CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(DATA_TYPE_STR_ALPHA), &alpha ); )
  CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(DATA_TYPE_STR_BETA), &beta ); )
  CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(unsigned int), &size0C ); )
#if SWITCH_AB
  CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(unsigned int), &size0B ); )
  CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(unsigned int), &size0A ); )
#else
    CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(unsigned int), &size0A ); )
    CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(unsigned int), &size0B ); )
#endif
  CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(unsigned int), &M ); )
  CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(unsigned int), &N ); )
  CHECK( clSetKernelArg( kernel_opencl, argIdx++, sizeof(unsigned int), &K ); )
  Timer timer;
  timer.start();
  for (unsigned int i = 0; i < numEnqueues; i++) {
    clEnqueueNDRangeKernel(queue, kernel_opencl,
        2, // num dims
        nullptr, // global offset
        globalSize,
        localSize,
        0, // num input events
        nullptr, // input events
        nullptr ); // output event
    }
#endif

  // wait for kernel
  printf("synchronizing stream\n");
#if Cobalt_BACKEND_HIP
  printf("synchronizing stream\n");
  status = hipStreamSynchronize( nullptr );
  CHECK(status);
#else
  CHECK( clFinish(queue); )
#endif
  double time_ms = timer.elapsed_ms() / numEnqueues;
  // copy result back to host
  printf("copying device results back to host\n");
#if Cobalt_BACKEND_HIP
  status = hipMemcpy( hC, dC, sizeC, hipMemcpyDeviceToHost ); CHECK(status);
#else
  CHECK( clEnqueueReadBuffer(queue, dC, CL_TRUE, 0, sizeC, hC, 0, nullptr, nullptr ); )
  CHECK( clFinish(queue); )
#endif

  size_t numInvalid = 0;
  printf("validating...\n");
#if VALIDATE

    sgemm_NT( transA, transB, hC_ref, hA, hB, alpha, beta, size0C, size0A, size0B, M, N, K );
    for (unsigned int i = 0; i < numElementsC; i++) {
      if (hC[i] != hC_ref[i]) {
        numInvalid++;
        if (numInvalid < 4*4) {
          printf("C[%u] = %f rather than %f\n", i, hC[i], hC_ref[i]);
        }
      }
    }

#else
  DATA_TYPE_STR_C answer = K*alpha + beta;
  for (unsigned int i = 0; i < numElementsC; i++) {
    if (hC[i] != answer) {
      numInvalid++;
      if (numInvalid < 4*4) {
        printf("C[%u] = %f rather than %f\n", i, hC[i], answer);
      }
    }
  }
#endif
  if (numInvalid) {
    printf("FAILED validation (%llu errors)\n", numInvalid);
  } else {
    printf("PASSED validation\n");
  }
  printf("t=%f ms\n", time_ms);

}

#if Cobalt_BACKEND_OPENCL12
void makeKernel(
    cl_kernel *kernel,
    cl_command_queue queue,
    const char *kernelSource,
    const char *sourceBuildOptions) {

  // get context and device from queue
  cl_int err;
  cl_context clContext;
  cl_device_id clDevice;
  CHECK( clGetCommandQueueInfo(queue, CL_QUEUE_CONTEXT, sizeof(clContext), &clContext, NULL); )
  CHECK( clGetCommandQueueInfo(queue, CL_QUEUE_DEVICE, sizeof(clDevice), &clDevice, NULL); )

  //printf("building kernel\n");
  cl_program clProgram;
  clProgram = clCreateProgramWithSource(
      clContext,
      1, &kernelSource,
      NULL, &err );
  CHECK(err)
  // driver leaks ~200kB at this call
  err = clBuildProgram(
      clProgram,
      1, &clDevice,
      sourceBuildOptions, NULL, NULL );
  CHECK(err)

  // print build failure
  if (err != CL_SUCCESS) {
    printf("clBuildProgram Failed; Error = %d\n", err);
    printf("\nKernel Source:\n\n");
    printf("%s\n", kernelSource);

    size_t len = 0;
    clGetProgramBuildInfo(clProgram, clDevice, CL_PROGRAM_BUILD_LOG, 0, NULL, &len);
    char* buildLog = new char[len];
    clGetProgramBuildInfo(clProgram, clDevice, CL_PROGRAM_BUILD_LOG, len*sizeof(char), buildLog, 0);
    printf("\n\n\nBuild Log:\n\n");
    printf("%s\n", buildLog);
    printf("\n");
    delete[] buildLog;
  }
  CHECK( clCreateKernelsInProgram(
      clProgram,
      1, kernel,
      NULL ); )
  CHECK( clReleaseProgram(clProgram); )

}

#endif



void sgemm_NT(
  bool transA,
  bool transB,
  float  *C,
  float  *A,
  float  *B,
  float const alpha,
  float const beta,
  unsigned int const ldc,
  unsigned int const lda,
  unsigned int const ldb,
  unsigned int const M,
  unsigned int const N,
  unsigned int const K ) {

  for (unsigned int i = 0; i < M; i++) {
    for (unsigned int j = 0; j < N; j++) {
      float c = 0.f;
      for (unsigned int k = 0; k < K; k++) {
        float a = transA ? A[k+i*lda] : A[i+k*lda];
        float b = transB ? B[j+k*ldb] : B[k+j*ldb];
        c += a*b;
      }
      size_t cIdx = i+j*ldc;
      C[cIdx] = alpha*c + beta*C[cIdx];
    }
  }
}

