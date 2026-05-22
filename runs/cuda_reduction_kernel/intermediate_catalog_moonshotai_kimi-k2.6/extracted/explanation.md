Here is a complete, self-contained CUDA C++ program that implements a multi-pass shared-memory reduction. It handles arbitrary input sizes (non-power-of-two), checks all CUDA API calls, and includes the requested test cases.

### `reduction.cu`
---

### Compile Command
*Adjust `-arch=sm_70` to match your GPU compute capability (e.g., `sm_61` for Pascal, `sm_80` for Ampere, etc.). The code itself does not require a specific architecture.*

---

### Explanation of Grid and Block Size Choices

- **Block size (256 threads):**  
  256 is a power of two, which makes the shared-memory tree reduction simple and exact (no extra bounds logic inside the reduction loop). It is also a multiple of the warp size (32), so no warps are partially wasted. This size tends to yield good occupancy on most NVIDIA GPUs while providing enough threads to amortize kernel launch overhead.

- **Grid size:**  
  The grid is sized as `(N + blockSize - 1) / blockSize` so that every input element is covered. Inside the kernel, a **grid-stride loop** lets each thread iterate across the array in steps of `gridDim.x * blockDim.x`. This keeps memory accesses coalesced, works for any `N` (even smaller than the grid), and gracefully handles the last block when `N` is not divisible by the block size.

---

### Explanation of How Partial Block Results Are Combined

1. **First pass:** Each block reduces its assigned elements to a single value using shared memory, then writes that partial sum to a unique slot in a temporary global array (`d_temp`).  
2. **Subsequent passes:** If there is more than one partial sum, the temporary array becomes the new input. Another reduction kernel is launched to sum those partial sums. This process repeats until only one value remains.  
3. **Final result:** The last remaining value in `d_temp` is copied back to the host.

This multi-pass approach avoids atomic operations on global memory, keeps the shared-memory reduction fast and deterministic, and naturally supports arbitrary input sizes because each pass is itself bounds-checked.
