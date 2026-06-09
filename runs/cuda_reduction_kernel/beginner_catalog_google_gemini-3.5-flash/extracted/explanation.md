Here is a complete, beginner-friendly CUDA C++ program that demonstrates how to sum an array of floating-point numbers on the GPU.

### 1. The CUDA Source Code (`main.cu`)

Save the following code as `main.cu`.
---

### 2. Compilation Command

To compile this program, you need the NVIDIA CUDA Toolkit installed. Run the following command in your terminal:
- `nvcc` is the NVIDIA CUDA Compiler.
- `-O3` enables compiler optimizations.
- `-o gpu_sum` specifies the output executable name.

To run the compiled program:
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
