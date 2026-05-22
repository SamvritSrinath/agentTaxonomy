## `sum_array.cu`
## Compile command
## Run command
Example output:
## Short explanation

The program creates an array of floats in CPU memory, then allocates matching memory on the GPU. The array is copied from the CPU to the GPU with `cudaMemcpy`.

The kernel is launched using many blocks, with 256 threads per block. Each thread reads one array element, but only if its global thread index is less than the array size. This prevents out-of-bounds memory reads.

Inside each block, threads store their values into shared memory. The block then performs a parallel reduction, where the number of active threads is repeatedly halved until one value remains. That value is the partial sum for the block. One thread from each block adds its partial sum to the final GPU result using `atomicAdd`.

Finally, the GPU sum is copied back to the CPU and printed next to a normal CPU-computed sum for comparison.
