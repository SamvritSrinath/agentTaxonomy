## `sum_array.cu`
## Compile command
## Run command
Example output:
## How the kernel works

The kernel launches many GPU threads. Each thread computes a global array index:
If that index is inside the input array, the thread loads one `float`. If the index is outside the array, it uses `0.0f` so it does not read past the end.

Each thread stores its value into shared memory. Threads in the same block then perform a parallel reduction: half the threads add pairs of values, then a quarter of the threads add pairs of partial sums, and so on. At the end, thread `0` in each block writes one partial sum to `d_partialSums`.

The program copies those partial sums back to the CPU and does the final small sum there. This keeps the CUDA example simple while still demonstrating GPU memory allocation, copying data to the GPU, running a kernel, and copying results back.
