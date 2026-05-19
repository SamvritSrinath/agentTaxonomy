Scenario: I am learning CUDA and want a simple example that sums an array of floating-point numbers on the GPU.

Goal: Write a complete CUDA program that demonstrates GPU memory allocation, copying data to the device, running a kernel, and copying the result back.

Task: Generate a CUDA C++ program that:
- Creates an array of float values on the CPU
- Allocates GPU memory
- Copies the array to the GPU
- Runs a kernel to help compute the sum
- Copies the result back to the CPU
- Prints the final sum

Requirements:
- Keep the code easy to read.
- Add comments explaining host memory, device memory, blocks, and threads.
- Make sure threads do not read beyond the end of the input array.
- Include a simple CPU-side sum so I can compare the result.

Deliverables:
- A complete .cu file
- The nvcc command to compile it
- A short explanation of how the kernel works
