## `reduction_sum.cu`
---

## Compile command
If your GPU is older or newer, adjust `-arch`, for example:
---

## Run command
---

## Expected output format

Exact numeric values may vary slightly by GPU and compiler because floating-point summation is not associative.

Example format:
---

## Correctness and safety explanation

### Public API
Behavior:

- `n == 0` returns `0.0f`.
- `n > 0 && host_input == nullptr` throws `std::invalid_argument`.
- CUDA failures throw `CudaException`.
- Size overflows throw `std::overflow_error`.

The function performs:

1. Host-to-device copy of the input.
2. One or more CUDA reduction kernel launches.
3. One final device-to-host copy of a single `float`.
4. Device memory cleanup.

Only one full input transfer and one final scalar transfer are performed.

---

### Bounds safety

The kernel uses a grid-stride loop:
Therefore:

- No global memory read occurs unless the index is `< n`.
- Non-power-of-two sizes are handled correctly.
- `n = 1` is handled correctly.
- Partial final blocks are handled correctly.
- Shared memory has exactly `BLOCK_SIZE` elements, and only `shared[tid]` and valid reduction partners are accessed.

---

### Synchronization safety

The kernel has two reduction phases:

1. Shared-memory block reduction across multiple warps.
2. Warp-level reduction using `__shfl_down_sync`.

Synchronization points:
This ensures all per-thread sums are visible before reduction begins.

Inside the shared-memory tree reduction:
Each iteration depends on values written by the previous iteration, so `__syncthreads()` is required and sufficient while multiple warps participate.

For the final warp, `__shfl_down_sync` is used. No block-wide synchronization is needed because only one warp participates.

There are no inter-block races because each block writes exactly one unique output element:
---

## Performance notes

### Block size

The implementation uses:
This is a common reduction block size because it gives:

- Enough threads per block for good occupancy.
- Moderate shared-memory usage.
- Efficient warp-level reduction.
- Two input elements per thread in the initial load pattern.

Each block processes up to `2 * BLOCK_SIZE` contiguous elements per grid-stride iteration.

---

### Memory coalescing

Within a block, threads read consecutive elements:
For a warp, these reads are contiguous, so global memory accesses are coalesced.

---

### Shared memory usage

Each block uses:
With `BLOCK_SIZE = 256`, this is only 1024 bytes per block.

Shared memory is used for the block-level tree reduction. The final warp reduction uses shuffle instructions to avoid unnecessary shared-memory traffic.

---

### Multi-pass reduction

A single kernel launch produces one partial sum per block.

If the input is large enough to require multiple blocks, the host repeatedly launches the same kernel on the partial sums until only one value remains.

This avoids inter-block synchronization inside a kernel, which CUDA does not provide globally for ordinary kernels.

---

### Why not one atomic per input element?

Using one global atomic add per input element would be a poor design because:

- All threads would contend on the same memory location.
- Atomic serialization would dominate runtime.
- Global memory atomics are far more expensive than register/shared-memory reductions.
- The memory system would be underutilized.

This implementation performs local reductions first and writes only one value per block, greatly reducing global synchronization pressure.

---

## Numerical limitations

Floating-point addition is not associative:
The GPU reduction tree sums values in a different order than the CPU reference implementation. Therefore, results may differ slightly.

The test harness compares against a double-precision CPU reference using a tolerance proportional to the sum of input magnitudes. This is especially important for mixed-magnitude inputs, where small values can be lost when added to very large values in single precision.
