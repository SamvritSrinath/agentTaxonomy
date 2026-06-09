Here is a complete, beginner-friendly CUDA C++ program that demonstrates how to sum an array of floating-point numbers on the GPU.

### 1. The CUDA Source Code (`main.cu`)

Save the following code as `main.cu`.

```cuda
#include <iostream>
#include <cmath>
#include <iomanip>
#include <cuda_runtime.h>

// CUDA Kernel to sum elements of an array.
// __global__ indicates that this function runs on the GPU (Device) but is called from the CPU (Host).
__global__ void sumKernel(const float* d_input, float* d_result, int n) {
    // Calculate the unique global thread index.
    // blockIdx.x:  The index of the current block in the grid.
    // blockDim.x:  The number of threads in each block.
    // threadIdx.x: The index of the current thread within its block.
    int idx = blockIdx.x * blockDim.x + threadIdx.x;

    // Out-of-bounds guard: Ensure we do not read past the end of the input array.
    // This is crucial when the array size (n) is not a perfect multiple of the block size.
    if (idx < n) {
        // atomicAdd safely adds the value to the destination address.
        // Because thousands of threads run in parallel, they might try to write to d_result
        // at the same time. atomicAdd serializes these writes to prevent race conditions.
        atomicAdd(d_result, d_input[idx]);
    }
}

// Helper function to compute the sum on the CPU for verification.
float computeCpuSum(const float* arr, int n) {
    double sum = 0.0; // Use double internally to minimize accumulation errors
    for (int i = 0; i < n; ++i) {
        sum += arr[i];
    }
    return static_cast<float>(sum);
}

int main() {
    // Number of elements in the array (1 Million)
    const int N = 1000000;
    const size_t size = N * sizeof(float);

    std::cout << "Initializing array of size " << N << "..." << std::endl;

    // --- HOST MEMORY ALLOCATION (CPU) ---
    // "h_" prefix denotes Host memory.
    float* h_input = (float*)malloc(size);
    float h_gpu_result = 0.0f;
    float h_cpu_result = 0.0f;

    // Initialize the host array with random float values between 0.0 and 1.0
    for (int i = 0; i < N; ++i) {
        h_input[i] = static_cast<float>(rand()) / static_cast<float>(RAND_MAX);
    }

    // --- DEVICE MEMORY ALLOCATION (GPU) ---
    // "d_" prefix denotes Device memory.
    float* d_input = nullptr;
    float* d_result = nullptr;

    // Allocate memory on the GPU
    cudaMalloc(&d_input, size);
    cudaMalloc(&d_result, sizeof(float));

    // --- DATA TRANSFER: HOST TO DEVICE ---
    // Copy the input array from CPU RAM to GPU VRAM
    cudaMemcpy(d_input, h_input, size, cudaMemcpyHostToDevice);
    
    // Initialize the GPU result variable to 0.0f
    cudaMemset(d_result, 0, sizeof(float));

    // --- KERNEL CONFIGURATION ---
    // Threads are grouped into "Blocks", and Blocks are grouped into a "Grid".
    int threadsPerBlock = 256;
    
    // Calculate the number of blocks needed to cover all N elements.
    // We use integer division rounding up to ensure we have enough threads.
    int blocksPerGrid = (N + threadsPerBlock - 1) / threadsPerBlock;

    std::cout << "Launching CUDA kernel with " << blocksPerGrid 
              << " blocks and " << threadsPerBlock << " threads per block..." << std::endl;

    // --- KERNEL LAUNCH ---
    // The <<<...>>> syntax configures the grid and block dimensions.
    sumKernel<<<blocksPerGrid, threadsPerBlock>>>(d_input, d_result, N);

    // Wait for the GPU to finish executing the kernel before proceeding
    cudaDeviceSynchronize();

    // Check for any errors during the kernel launch or execution
    cudaError_t err = cudaGetLastError();
    if (err != cudaSuccess) {
        std::cerr << "CUDA Error: " << cudaGetErrorString(err) << std::endl;
        return -1;
    }

    // --- DATA TRANSFER: DEVICE TO HOST ---
    // Copy the final sum back from GPU VRAM to CPU RAM
    cudaMemcpy(&h_gpu_result, d_result, sizeof(float), cudaMemcpyDeviceToHost);

    // --- VERIFICATION ---
    std::cout << "Computing sum on CPU for verification..." << std::endl;
    h_cpu_result = computeCpuSum(h_input, N);

    // Print results
    std::cout << std::fixed << std::setprecision(3);
    std::cout << "\n--- Results ---" << std::endl;
    std::cout << "GPU Sum: " << h_gpu_result << std::endl;
    std::cout << "CPU Sum: " << h_cpu_result << std::endl;
    
    // Note: A tiny difference is normal due to the non-associative nature of floating-point addition
    // when performed in a different order on the GPU vs. CPU.
    float difference = std::abs(h_gpu_result - h_cpu_result);
    std::cout << "Absolute Difference: " << difference << std::endl;

    // --- CLEANUP ---
    // Free GPU memory
    cudaFree(d_input);
    cudaFree(d_result);

    // Free CPU memory
    free(h_input);

    std::cout << "\nMemory successfully freed. Program finished." << std::endl;
    return 0;
}
```

---

### 2. Compilation Command

To compile this program, you need the NVIDIA CUDA Toolkit installed. Run the following command in your terminal:

```bash
nvcc -O3 main.cu -o gpu_sum
```

- `nvcc` is the NVIDIA CUDA Compiler.
- `-O3` enables compiler optimizations.
- `-o gpu_sum` specifies the output executable name.

To run the compiled program:
```bash
./gpu_sum
```

---

### 3. How the Kernel Works

1. **Thread Indexing**: 
   CUDA executes the kernel function (`sumKernel`) thousands of times in parallel. To know which element of the array to process, each thread calculates its unique global ID using:
   $$\text{idx} = \text{blockIdx.x} \times \text{blockDim.x} + \text{threadIdx.x}$$
   This maps each thread to a specific index in the array.

2. **Out-of-Bounds Guard**:
   Because we launch blocks in groups of 256 threads, the total number of threads might be slightly larger than our array size $N$. The condition `if (idx < n)` ensures that any "extra" threads at the end of the grid do not attempt to read memory outside the array boundaries, preventing segmentation faults.

3. **Atomic Addition (`atomicAdd`)**:
   Normally, if multiple threads try to write to the same memory address simultaneously, a **race condition** occurs, resulting in corrupted data. 
   `atomicAdd(d_result, d_input[idx])` guarantees that the addition is performed safely. The GPU hardware serializes the additions to `d_result` so that no two threads interfere with each other. *(Note: While there are faster reduction algorithms using shared memory, `atomicAdd` is the simplest and most readable way to introduce parallel accumulation).*
