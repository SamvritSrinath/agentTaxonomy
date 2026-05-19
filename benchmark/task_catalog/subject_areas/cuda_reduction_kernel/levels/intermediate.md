Scenario: I need a CUDA C++ reduction implementation that sums a large float array and validates the result against a CPU implementation. The input size may not be a power of two.

Goal: Implement a correct and reasonably efficient GPU reduction using shared memory.

Task: Generate a complete CUDA C++ program that includes:
- A block-level reduction kernel using shared memory
- Host-side launcher code
- CPU reference implementation
- Result comparison using a numerical tolerance
- Tests for several input sizes

Requirements:
- Support arbitrary input lengths, including non-power-of-two sizes.
- Avoid out-of-bounds global memory access.
- Avoid out-of-bounds shared memory access.
- Use __syncthreads() correctly during shared-memory reduction.
- Correctly combine partial sums from multiple blocks.
- Check CUDA API errors after allocation, memory copies, and kernel launch.
- Free all allocated device memory.

Test Cases:
- Small array
- Array with one element
- Non-power-of-two array length
- Large array
- Array containing negative values

Deliverables:
- One complete .cu file
- Compile command using nvcc
- Explanation of grid size and block size choices
- Explanation of how partial block results are combined

Acceptance Criteria:
- The GPU result should match the CPU result within a reasonable floating-point tolerance.
- The code should not assume that the input length is divisible by the block size
