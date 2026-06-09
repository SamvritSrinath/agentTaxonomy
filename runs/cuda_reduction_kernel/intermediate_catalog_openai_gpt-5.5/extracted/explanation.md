## `reduction_shared.cu`
## Compile
Optionally specify your GPU architecture, for example:
## Run
## Explanation

- `BLOCK_SIZE` is `256`, a power of two, which simplifies the shared-memory tree reduction.
- Each thread initially loads up to two global-memory elements:
  - `input[base]`
  - `input[base + blockDim.x]`
- Therefore each block reduces up to `2 * BLOCK_SIZE`, or `512`, input elements.
- The grid size is computed as:
so the code does not require `n` to be divisible by the block size or to be a power of two.

Bounds checks are used before every global-memory read:
Shared memory is allocated with exactly `BLOCK_SIZE` floats, and the reduction loop only accesses valid indices from `0` to `BLOCK_SIZE - 1`.

Partial block results are written to a temporary device array. If more than one partial result remains, the same reduction kernel is launched again on the partial sums. This repeats until only one value remains, which is copied back to the host and compared against a CPU reference sum using a floating-point tolerance.
