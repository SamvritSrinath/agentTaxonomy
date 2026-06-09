## `sum_array.cu`

```cpp
#include <cuda_runtime.h>

#include <cmath>
#include <cstdlib>
#include <iostream>
#include <vector>

// Simple CUDA error-checking helper
#define CUDA_CHECK(call)                                                       \
    do {                                                                       \
        cudaError_t err = (call);                                               \
        if (err != cudaSuccess) {                                               \
            std::cerr << "CUDA error at " << __FILE__ << ":" << __LINE__       \
                      << " - " << cudaGetErrorString(err) << std::endl;        \
            std::exit(EXIT_FAILURE);                                           \
        }                                                                      \
    } while (0)

// Kernel: each block computes a partial sum of the input array.
//
// Host memory:
//   Memory allocated on the CPU, such as std::vector<float> h_input.
//
// Device memory:
//   Memory allocated on the GPU with cudaMalloc, such as d_input.
//
// Blocks and threads:
//   A CUDA kernel is launched as a grid of blocks.
//   Each block contains many threads.
//   Here, each thread loads one array element, then threads in the same block
//   cooperate to reduce those values into one partial sum.
__global__ void sumKernel(const float* input, float* partialSums, int n) {
    // Shared memory is memory shared by all threads in the same block.
    extern __shared__ float sharedData[];

    unsigned int threadId = threadIdx.x;

    // Compute the global index handled by this thread.
    unsigned int globalIndex = blockIdx.x * blockDim.x + threadIdx.x;

    // Make sure we do not read beyond the end of the input array.
    float value = 0.0f;
    if (globalIndex < n) {
        value = input[globalIndex];
    }

    // Store each thread's value into shared memory.
    sharedData[threadId] = value;
    __syncthreads();

    // Parallel reduction inside one block.
    // After this loop, sharedData[0] contains the sum for this block.
    for (unsigned int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (threadId < stride) {
            sharedData[threadId] += sharedData[threadId + stride];
        }

        // Make sure all threads have finished this reduction step
        // before starting the next one.
        __syncthreads();
    }

    // One thread writes the block's partial sum to device memory.
    if (threadId == 0) {
        partialSums[blockIdx.x] = sharedData[0];
    }
}

int main() {
    const int n = 1 << 20; // 1,048,576 floats

    // -----------------------------
    // Allocate and initialize host memory.
    // Host memory lives on the CPU.
    // -----------------------------
    std::vector<float> h_input(n);

    for (int i = 0; i < n; ++i) {
        h_input[i] = 1.0f;
    }

    // CPU-side sum for comparison.
    float cpuSum = 0.0f;
    for (int i = 0; i < n; ++i) {
        cpuSum += h_input[i];
    }

    // -----------------------------
    // Allocate device memory.
    // Device memory lives on the GPU.
    // -----------------------------
    float* d_input = nullptr;
    float* d_partialSums = nullptr;

    const int threadsPerBlock = 256;
    const int blocksPerGrid = (n + threadsPerBlock - 1) / threadsPerBlock;

    CUDA_CHECK(cudaMalloc(&d_input, n * sizeof(float)));
    CUDA_CHECK(cudaMalloc(&d_partialSums, blocksPerGrid * sizeof(float)));

    // -----------------------------
    // Copy input data from host memory to device memory.
    // -----------------------------
    CUDA_CHECK(cudaMemcpy(
        d_input,
        h_input.data(),
        n * sizeof(float),
        cudaMemcpyHostToDevice
    ));

    // -----------------------------
    // Launch the kernel.
    //
    // blocksPerGrid: number of blocks in the grid
    // threadsPerBlock: number of threads in each block
    // threadsPerBlock * sizeof(float): shared memory size per block
    // -----------------------------
    sumKernel<<<blocksPerGrid, threadsPerBlock, threadsPerBlock * sizeof(float)>>>(
        d_input,
        d_partialSums,
        n
    );

    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());

    // -----------------------------
    // Copy partial sums back from device memory to host memory.
    // -----------------------------
    std::vector<float> h_partialSums(blocksPerGrid);

    CUDA_CHECK(cudaMemcpy(
        h_partialSums.data(),
        d_partialSums,
        blocksPerGrid * sizeof(float),
        cudaMemcpyDeviceToHost
    ));

    // Finish the final sum on the CPU by summing the block partial sums.
    float gpuSum = 0.0f;
    for (int i = 0; i < blocksPerGrid; ++i) {
        gpuSum += h_partialSums[i];
    }

    std::cout << "CPU sum: " << cpuSum << std::endl;
    std::cout << "GPU sum: " << gpuSum << std::endl;
    std::cout << "Difference: " << std::fabs(cpuSum - gpuSum) << std::endl;

    // -----------------------------
    // Free device memory.
    // -----------------------------
    CUDA_CHECK(cudaFree(d_input));
    CUDA_CHECK(cudaFree(d_partialSums));

    return 0;
}
```

## Compile command

```bash
nvcc -O2 sum_array.cu -o sum_array
```

## Run command

```bash
./sum_array
```

Example output:

```text
CPU sum: 1.04858e+06
GPU sum: 1.04858e+06
Difference: 0
```

## How the kernel works

The kernel launches many GPU threads. Each thread computes a global array index:

```cpp
globalIndex = blockIdx.x * blockDim.x + threadIdx.x;
```

If that index is inside the input array, the thread loads one `float`. If the index is outside the array, it uses `0.0f` so it does not read past the end.

Each thread stores its value into shared memory. Threads in the same block then perform a parallel reduction: half the threads add pairs of values, then a quarter of the threads add pairs of partial sums, and so on. At the end, thread `0` in each block writes one partial sum to `d_partialSums`.

The program copies those partial sums back to the CPU and does the final small sum there. This keeps the CUDA example simple while still demonstrating GPU memory allocation, copying data to the GPU, running a kernel, and copying results back.
