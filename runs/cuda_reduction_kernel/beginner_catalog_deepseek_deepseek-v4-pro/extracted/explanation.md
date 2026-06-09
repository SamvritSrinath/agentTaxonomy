Below is a complete CUDA program that sums an array of floats on the GPU using a parallel reduction kernel. It includes host/device memory management, a CPU‑side sum for verification, and detailed comments.

### File: `sum_array.cu`
### Compilation

Use the NVIDIA CUDA compiler `nvcc`:
Run the executable:
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
