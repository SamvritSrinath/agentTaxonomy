**Compile command**
**Explanation of grid size and block size choices**

- **Block size** is fixed to **256** threads. This is a typical power-of‑two value that gives good occupancy on all modern CUDA GPUs while keeping the shared memory reduction loop simple (only works correctly with power-of‑two block sizes).

- **Grid size** for the first pass is `ceilDiv(N, blockSize)`, clamped to `maxGridSize[0]` of the device. If `N` is small, the grid has a single block. For very large `N` (e.g., tens of millions), the grid is capped, and the resulting partial sums are further reduced in subsequent passes.

- **Why not assume `N % blockSize == 0`?** The kernel handles any length by loading a zero for threads whose global index falls beyond `N`. The reduction then naturally incorporates those zeros, so no special padding is needed on the host side. The grid is computed with a ceiling division that guarantees all input elements are covered, and no out‑of‑bounds global memory reads occur because of the explicit `if (globalIdx < N)` check.

**How partial block results are combined**

The program uses an iterative on‑device reduction:

1. The first call to `sumReductionKernel` processes the whole input array. Each block computes a partial sum of its segment and writes it to a dedicated output array (size = number of blocks).

2. After synchronisation, the number of partial values becomes the new “problem size”. The roles of the two device buffers are swapped.

3. If the new size is still larger than 1, the kernel is launched again, now reading the partial‑sum array as input and writing an even smaller set of partial sums.

4. This process repeats until exactly one value remains, which is the final sum.

This hierarchical strategy gracefully handles any initial array length and naturally respects the device’s `maxGridSize` limit. All buffer management (allocation, pointer swaps, and final copy) is done on the host, and every CUDA API call is checked for errors.
