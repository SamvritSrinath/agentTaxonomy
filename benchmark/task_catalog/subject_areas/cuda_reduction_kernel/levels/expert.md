Scenario: I need a reusable CUDA C++ reduction primitive for summing large float arrays. This may later be used inside a performance-sensitive inference or HPC pipeline, so the implementation should be correct, maintainable, and explicit about its assumptions.

Goal: Produce a production-quality CUDA reduction module with a clean host API, robust error handling, validation tests, and a short correctness/performance explanation.

Public API:
- Implement a host function with this shape: float gpu_reduce_sum(const float* host_input, size_t n)
- The function should allocate device memory, launch the required kernels, return the final sum, and clean up resources.
- Clearly document how errors are reported. If you choose exceptions, use them consistently. If you choose error codes, define the API clearly.

Kernel Requirements:
- Correctly handle n = 0 and n = 1.
- Correctly handle arbitrary input sizes and non-power-of-two lengths.
- Avoid out-of-bounds global memory reads.
- Avoid out-of-bounds shared memory access.
- Use efficient block-level reduction.
- Use warp-level primitives where appropriate, but keep the implementation understandable.
- Correctly combine partial sums across multiple blocks.
- Avoid race conditions.
- Explain the synchronization points and why they are sufficient.

Host-Side Requirements:
- Check every CUDA API call.
- Check kernel launch errors.
- Handle allocation failure cleanly.
- Avoid memory leaks on success and failure paths.
- Avoid unnecessary host-device transfers.
- Guard size calculations against overflow where relevant.

Validation Requirements:
- Include a CPU reference implementation.
- Compare GPU and CPU results using a tolerance appropriate for floating-point summation.
- Include tests for:
- n = 0
- n = 1
- Small arrays
- Non-power-of-two sizes
- Large arrays
- Arrays with negative values
- Arrays with mixed-magnitude values

Performance Notes:
- Explain block size selection.
- Explain memory coalescing behavior.
- Explain shared memory usage.
- Explain when a multi-pass reduction is needed.
- Discuss why using one atomic operation per input element would be a poor design.
- Briefly discuss floating-point non-associativity and why GPU and CPU sums may differ slightly.

Deliverables:
- Complete .cu source file
- Compile command using nvcc
- Test cases inside the program or in a small test harness
- Expected output format
- Explanation of correctness, bounds safety, synchronization safety, and numerical limitations
