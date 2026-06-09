Below is a complete CUDA program that sums an array of floats on the GPU using a parallel reduction kernel. It includes host/device memory management, a CPU‑side sum for verification, and detailed comments.

### File: `sum_array.cu`

```cpp
#include <stdio.h>
#include <stdlib.h>
#include <cuda_runtime.h>

// ---------------------------------------------------------------------------
// GPU kernel: parallel reduction inside each block
// Each block computes the sum of its assigned segment and writes the result
// to d_partial_sums[blockIdx.x].
// ---------------------------------------------------------------------------
__global__ void reduceSum(const float *d_in, float *d_partial_sums, int N) {
    // Shared memory for block-level reduction
    extern __shared__ float sdata[];

    // Global thread index
    int tid = threadIdx.x;
    int idx = blockIdx.x * blockDim.x + threadIdx.x;

    // Load element into shared memory, using 0 for out-of-bounds threads
    sdata[tid] = (idx < N) ? d_in[idx] : 0.0f;
    __syncthreads();

    // Perform reduction in shared memory (tree‑based)
    for (int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            sdata[tid] += sdata[tid + stride];
        }
        __syncthreads();  // ensure all additions in this step are done
    }

    // Thread 0 of each block writes the block's partial sum to global memory
    if (tid == 0) {
        d_partial_sums[blockIdx.x] = sdata[0];
    }
}

// ---------------------------------------------------------------------------
// Simple CPU sum for verification
// ---------------------------------------------------------------------------
float cpuSum(const float *data, int N) {
    float sum = 0.0f;
    for (int i = 0; i < N; i++) {
        sum += data[i];
    }
    return sum;
}

// ---------------------------------------------------------------------------
// Utility macro for CUDA error checking
// ---------------------------------------------------------------------------
#define CUDA_CHECK(call) \
    do { \
        cudaError_t err = call; \
        if (err != cudaSuccess) { \
            fprintf(stderr, "CUDA error at %s:%d - %s\n", __FILE__, __LINE__, \
                    cudaGetErrorString(err)); \
            exit(EXIT_FAILURE); \
        } \
    } while(0)

// ---------------------------------------------------------------------------
int main() {
    // Problem size: number of elements in the array
    const int N = 1 << 20;  // 1M elements
    const size_t bytes = N * sizeof(float);

    // ---- Host memory allocation ----
    // h_data: array on the CPU (host)
    float *h_data = (float*)malloc(bytes);
    if (!h_data) {
        fprintf(stderr, "Host memory allocation failed\n");
        return EXIT_FAILURE;
    }

    // Initialize the array with some values (e.g., 1.0f, 2.0f, ...)
    for (int i = 0; i < N; i++) {
        h_data[i] = (float)(i + 1);  // sum = N*(N+1)/2
    }

    // ---- Device memory allocation ----
    // d_data: array on the GPU (device)
    float *d_data;
    CUDA_CHECK(cudaMalloc(&d_data, bytes));

    // d_partial_sums: will hold one partial sum per block
    // We need enough blocks to cover N elements.
    int threadsPerBlock = 256;
    int blocksPerGrid = (N + threadsPerBlock - 1) / threadsPerBlock;
    float *d_partial_sums;
    CUDA_CHECK(cudaMalloc(&d_partial_sums, blocksPerGrid * sizeof(float)));

    // ---- Copy input data from host to device ----
    CUDA_CHECK(cudaMemcpy(d_data, h_data, bytes, cudaMemcpyHostToDevice));

    // ---- Launch the reduction kernel ----
    // Shared memory size: threadsPerBlock * sizeof(float)
    reduceSum<<<blocksPerGrid, threadsPerBlock, threadsPerBlock * sizeof(float)>>>(
        d_data, d_partial_sums, N);
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());

    // ---- Copy partial sums back to host ----
    float *h_partial_sums = (float*)malloc(blocksPerGrid * sizeof(float));
    CUDA_CHECK(cudaMemcpy(h_partial_sums, d_partial_sums,
                          blocksPerGrid * sizeof(float), cudaMemcpyDeviceToHost));

    // ---- Final reduction on the CPU (sum the partial sums) ----
    float gpuSum = 0.0f;
    for (int i = 0; i < blocksPerGrid; i++) {
        gpuSum += h_partial_sums[i];
    }

    // ---- CPU sum for comparison ----
    float cpuResult = cpuSum(h_data, N);

    // ---- Print results ----
    printf("Array size: %d\n", N);
    printf("CPU sum:    %f\n", cpuResult);
    printf("GPU sum:    %f\n", gpuSum);
    printf("Difference: %e\n", fabs(cpuResult - gpuSum));

    // ---- Cleanup ----
    free(h_data);
    free(h_partial_sums);
    cudaFree(d_data);
    cudaFree(d_partial_sums);

    return 0;
}
```

### Compilation

Use the NVIDIA CUDA compiler `nvcc`:

```bash
nvcc -o sum_array sum_array.cu
```

Run the executable:

```bash
./sum_array
```

### How the Kernel Works

1. **Grid and Block Layout**  
   - The array of `N` elements is divided among a 1D grid of blocks.  
   - Each block contains `threadsPerBlock` threads (here 256).  
   - The number of blocks is `ceil(N / threadsPerBlock)`, ensuring every element is covered.

2. **Shared Memory Reduction**  
   - Each block uses **shared memory** (`extern __shared__ float sdata[]`) to hold the values of its assigned segment.  
   - Every thread loads one element from global memory into `sdata`. If the global index is beyond `N`, it loads `0.0f` to avoid out‑of‑bounds access.  
   - `__syncthreads()` ensures all loads complete before the reduction begins.

3. **Tree‑Based Reduction**  
   - The reduction loop halves the active threads each iteration (`stride` starts at half the block size).  
   - Only threads with `tid < stride` add the value from `sdata[tid + stride]` to their own.  
   - After each addition, `__syncthreads()` guarantees that all threads have finished the current level before the next stride.  
   - After the loop, `sdata[0]` holds the sum of the block’s segment.

4. **Storing Partial Sums**  
   - Thread 0 of each block writes `sdata[0]` to `d_partial_sums[blockIdx.x]`.  
   - This array contains one partial sum per block.

5. **Final Sum on the CPU**  
   - The host copies the partial sums back and adds them together.  
   - This final step is trivial and avoids launching another kernel.

6. **Boundary Safety**  
   - The condition `(idx < N) ? d_in[idx] : 0.0f` guarantees that threads never read beyond the allocated array.  
   - The grid is sized so that every element is covered, and extra threads simply contribute zero.

This design is a classic introduction to CUDA concepts: host/device memory, kernel launch configuration, shared memory, thread synchronization, and parallel reduction. The CPU sum provides a straightforward correctness check.
