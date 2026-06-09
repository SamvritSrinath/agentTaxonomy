## `reduction_sum.cu`

```cuda
// reduction_sum.cu
//
// Production-oriented CUDA C++ reduction primitive for summing float arrays.
//
// Public API:
//   float gpu_reduce_sum(const float* host_input, size_t n)
//
// Error reporting:
//   This module uses C++ exceptions consistently.
//   - CUDA API failures throw CudaException.
//   - Invalid host arguments throw std::invalid_argument.
//   - Size calculation overflow throws std::overflow_error.
//
// Build example:
//   nvcc -O3 -std=c++17 -arch=sm_70 reduction_sum.cu -o reduction_sum
//
// Run:
//   ./reduction_sum

#include <cuda_runtime.h>

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

namespace cuda_reduction {

constexpr int kBlockSize = 256;

// -----------------------------
// Error handling
// -----------------------------

class CudaException final : public std::runtime_error {
public:
    explicit CudaException(const std::string& msg) : std::runtime_error(msg) {}
};

inline void cuda_check(cudaError_t status,
                       const char* expr,
                       const char* file,
                       int line) {
    if (status != cudaSuccess) {
        std::string msg = "CUDA error at ";
        msg += file;
        msg += ":";
        msg += std::to_string(line);
        msg += " while evaluating ";
        msg += expr;
        msg += ": ";
        msg += cudaGetErrorString(status);
        throw CudaException(msg);
    }
}

#define CUDA_CHECK(expr) ::cuda_reduction::cuda_check((expr), #expr, __FILE__, __LINE__)

// RAII device buffer.
// Normal success paths explicitly free with release_checked() so cudaFree errors
// are reported. The destructor is noexcept and acts as a leak-prevention fallback
// during stack unwinding.
class DeviceBuffer {
public:
    DeviceBuffer() = default;

    explicit DeviceBuffer(size_t bytes) {
        allocate(bytes);
    }

    DeviceBuffer(const DeviceBuffer&) = delete;
    DeviceBuffer& operator=(const DeviceBuffer&) = delete;

    DeviceBuffer(DeviceBuffer&& other) noexcept : ptr_(other.ptr_) {
        other.ptr_ = nullptr;
    }

    DeviceBuffer& operator=(DeviceBuffer&& other) noexcept {
        if (this != &other) {
            if (ptr_ != nullptr) {
                // Destructor-style cleanup: cannot throw here.
                (void)cudaFree(ptr_);
            }
            ptr_ = other.ptr_;
            other.ptr_ = nullptr;
        }
        return *this;
    }

    ~DeviceBuffer() {
        if (ptr_ != nullptr) {
            // Cannot throw from destructor. Explicit success paths call
            // release_checked(); this fallback prevents leaks on exceptions.
            (void)cudaFree(ptr_);
        }
    }

    void allocate(size_t bytes) {
        if (bytes == 0) {
            ptr_ = nullptr;
            return;
        }

        if (ptr_ != nullptr) {
            throw std::logic_error("DeviceBuffer::allocate called on non-empty buffer");
        }

        CUDA_CHECK(cudaMalloc(&ptr_, bytes));
    }

    void release_checked() {
        if (ptr_ != nullptr) {
            void* p = ptr_;
            ptr_ = nullptr;
            CUDA_CHECK(cudaFree(p));
        }
    }

    void* get() const {
        return ptr_;
    }

    float* as_float() const {
        return static_cast<float*>(ptr_);
    }

private:
    void* ptr_ = nullptr;
};

inline size_t checked_float_bytes(size_t count) {
    if (count > std::numeric_limits<size_t>::max() / sizeof(float)) {
        throw std::overflow_error("float byte-size calculation overflow");
    }
    return count * sizeof(float);
}

inline int choose_grid_blocks(size_t element_count, int max_grid_x) {
    if (element_count == 0) {
        return 0;
    }

    constexpr size_t elems_per_block = static_cast<size_t>(kBlockSize) * 2;

    // Avoid overflow from element_count + elems_per_block - 1.
    size_t required = ((element_count - 1) / elems_per_block) + 1;
    size_t capped = std::min(required, static_cast<size_t>(max_grid_x));

    if (capped == 0 || capped > static_cast<size_t>(std::numeric_limits<int>::max())) {
        throw std::overflow_error("invalid CUDA grid size");
    }

    return static_cast<int>(capped);
}

// -----------------------------
// CUDA kernel
// -----------------------------

template <int BLOCK_SIZE>
__global__ void reduce_sum_kernel(const float* __restrict__ input,
                                  float* __restrict__ output,
                                  size_t n) {
    extern __shared__ float shared[];

    const unsigned int tid = threadIdx.x;

    // Each thread initially consumes up to two contiguous elements.
    // The grid-stride loop lets a fixed/capped grid handle arrays larger than
    // gridDim.x * BLOCK_SIZE * 2.
    size_t idx = static_cast<size_t>(blockIdx.x) * BLOCK_SIZE * 2 + tid;
    const size_t stride = static_cast<size_t>(gridDim.x) * BLOCK_SIZE * 2;

    float local_sum = 0.0f;

    while (idx < n) {
        local_sum += input[idx];

        const size_t second = idx + BLOCK_SIZE;
        if (second < n) {
            local_sum += input[second];
        }

        idx += stride;
    }

    // One shared-memory slot per thread. tid is always in [0, BLOCK_SIZE).
    shared[tid] = local_sum;
    __syncthreads();

    // Block-level tree reduction in shared memory.
    //
    // Synchronization rationale:
    // - After writing shared[tid], all threads must synchronize before any
    //   thread reads another thread's value.
    // - Each shared-memory reduction step reads values written in the previous
    //   step, so a __syncthreads() is required between steps while more than
    //   one warp participates.
    for (unsigned int offset = BLOCK_SIZE / 2; offset > 32; offset >>= 1) {
        if (tid < offset) {
            shared[tid] += shared[tid + offset];
        }
        __syncthreads();
    }

    // Final 64 -> 32 reduction and warp reduction.
    // At this point only one warp participates, so warp shuffle operations are
    // sufficient. Threads in a warp execute in lockstep, and __shfl_down_sync
    // provides the necessary warp-level synchronization.
    if (tid < 32) {
        float value = shared[tid];

        if constexpr (BLOCK_SIZE >= 64) {
            value += shared[tid + 32];
        }

        unsigned int mask = 0xffffffffu;
        value += __shfl_down_sync(mask, value, 16);
        value += __shfl_down_sync(mask, value, 8);
        value += __shfl_down_sync(mask, value, 4);
        value += __shfl_down_sync(mask, value, 2);
        value += __shfl_down_sync(mask, value, 1);

        if (tid == 0) {
            output[blockIdx.x] = value;
        }
    }
}

// -----------------------------
// Public host API
// -----------------------------

float gpu_reduce_sum(const float* host_input, size_t n) {
    if (n == 0) {
        return 0.0f;
    }

    if (host_input == nullptr) {
        throw std::invalid_argument("gpu_reduce_sum: host_input is null while n > 0");
    }

    const size_t input_bytes = checked_float_bytes(n);

    int device = 0;
    CUDA_CHECK(cudaGetDevice(&device));

    int max_grid_x = 0;
    CUDA_CHECK(cudaDeviceGetAttribute(&max_grid_x, cudaDevAttrMaxGridDimX, device));

    if (max_grid_x <= 0) {
        throw CudaException("invalid cudaDevAttrMaxGridDimX");
    }

    const int initial_blocks = choose_grid_blocks(n, max_grid_x);
    const size_t partial_capacity = static_cast<size_t>(initial_blocks);
    const size_t partial_bytes = checked_float_bytes(partial_capacity);

    DeviceBuffer d_input(input_bytes);
    DeviceBuffer d_partial_a(partial_bytes);
    DeviceBuffer d_partial_b;

    if (partial_capacity > 1) {
        d_partial_b.allocate(partial_bytes);
    }

    CUDA_CHECK(cudaMemcpy(d_input.get(),
                          host_input,
                          input_bytes,
                          cudaMemcpyHostToDevice));

    const size_t shared_bytes = static_cast<size_t>(kBlockSize) * sizeof(float);

    // First pass: reduce original input into partial sums.
    reduce_sum_kernel<kBlockSize>
        <<<initial_blocks, kBlockSize, shared_bytes>>>(
            static_cast<const float*>(d_input.get()),
            d_partial_a.as_float(),
            n);

    CUDA_CHECK(cudaGetLastError());

    size_t current_count = partial_capacity;
    const float* current_input = d_partial_a.as_float();
    float* current_output = d_partial_b.as_float();

    // Additional passes: reduce partial sums until one value remains.
    while (current_count > 1) {
        const int blocks = choose_grid_blocks(current_count, max_grid_x);

        reduce_sum_kernel<kBlockSize>
            <<<blocks, kBlockSize, shared_bytes>>>(
                current_input,
                current_output,
                current_count);

        CUDA_CHECK(cudaGetLastError());

        current_count = static_cast<size_t>(blocks);
        current_input = current_output;

        // Ping-pong between partial buffers.
        current_output = (current_output == d_partial_a.as_float())
                             ? d_partial_b.as_float()
                             : d_partial_a.as_float();
    }

    float result = 0.0f;

    // This copy also synchronizes with the preceding kernels and will report
    // asynchronous kernel execution errors, if any.
    CUDA_CHECK(cudaMemcpy(&result,
                          current_input,
                          sizeof(float),
                          cudaMemcpyDeviceToHost));

    // Explicit checked cleanup on the success path.
    d_partial_b.release_checked();
    d_partial_a.release_checked();
    d_input.release_checked();

    return result;
}

// -----------------------------
// CPU reference implementation
// -----------------------------

double cpu_reduce_sum_reference(const float* input, size_t n) {
    double sum = 0.0;
    for (size_t i = 0; i < n; ++i) {
        sum += static_cast<double>(input[i]);
    }
    return sum;
}

double cpu_sum_abs_reference(const float* input, size_t n) {
    double sum_abs = 0.0;
    for (size_t i = 0; i < n; ++i) {
        sum_abs += std::abs(static_cast<double>(input[i]));
    }
    return sum_abs;
}

double validation_tolerance(size_t n, double reference, double sum_abs) {
    if (n == 0) {
        return 0.0;
    }

    // GPU and CPU summation orders differ. A tolerance proportional to the
    // total magnitude is appropriate for single-precision reduction tests.
    //
    // This is intentionally conservative for mixed-magnitude arrays, where
    // non-associativity can dominate.
    const double abs_floor = 1.0e-4;
    const double rel_to_abs_sum = 1.0e-5 * std::max(1.0, sum_abs);
    const double rel_to_result = 1.0e-5 * std::max(1.0, std::abs(reference));

    return abs_floor + std::max(rel_to_abs_sum, rel_to_result);
}

bool run_test(const std::string& name, const std::vector<float>& data) {
    const float* ptr = data.empty() ? nullptr : data.data();

    const float gpu = gpu_reduce_sum(ptr, data.size());
    const double cpu = cpu_reduce_sum_reference(ptr, data.size());
    const double sum_abs = cpu_sum_abs_reference(ptr, data.size());

    const double err = std::abs(static_cast<double>(gpu) - cpu);
    const double tol = validation_tolerance(data.size(), cpu, sum_abs);

    const bool pass = err <= tol;

    std::cout << (pass ? "[PASS] " : "[FAIL] ")
              << std::left << std::setw(28) << name
              << " n=" << std::setw(10) << data.size()
              << " gpu=" << std::setw(16) << std::setprecision(9) << gpu
              << " cpu=" << std::setw(16) << std::setprecision(12) << cpu
              << " abs_err=" << std::setw(14) << std::setprecision(6) << err
              << " tol=" << std::setprecision(6) << tol
              << "\n";

    return pass;
}

}  // namespace cuda_reduction

// -----------------------------
// Test harness
// -----------------------------

int main() {
    using namespace cuda_reduction;

    try {
        std::vector<std::pair<std::string, std::vector<float>>> tests;

        tests.emplace_back("n = 0", std::vector<float>{});
        tests.emplace_back("n = 1", std::vector<float>{42.5f});
        tests.emplace_back("small array", std::vector<float>{1.0f, 2.0f, 3.0f, 4.0f, 5.0f});
        tests.emplace_back("negative values",
                           std::vector<float>{-1.0f, -2.5f, -3.25f, -4.75f, -5.125f});

        {
            std::vector<float> v(1003);
            for (size_t i = 0; i < v.size(); ++i) {
                v[i] = static_cast<float>((static_cast<int>(i % 17) - 8) * 0.25f);
            }
            tests.emplace_back("non-power-of-two", std::move(v));
        }

        {
            constexpr size_t n = (1u << 20) + 123;
            std::vector<float> v(n);

            std::mt19937 rng(12345);
            std::uniform_real_distribution<float> dist(-1.0f, 1.0f);

            for (float& x : v) {
                x = dist(rng);
            }

            tests.emplace_back("large random array", std::move(v));
        }

        {
            std::vector<float> v(10007);
            for (size_t i = 0; i < v.size(); ++i) {
                switch (i % 4) {
                    case 0: v[i] = 1.0e8f; break;
                    case 1: v[i] = 1.0f; break;
                    case 2: v[i] = -1.0e8f; break;
                    default: v[i] = -1.0f; break;
                }
            }
            tests.emplace_back("mixed magnitudes", std::move(v));
        }

        bool all_passed = true;

        for (const auto& test : tests) {
            all_passed = run_test(test.first, test.second) && all_passed;
        }

        std::cout << "\nResult: " << (all_passed ? "ALL TESTS PASSED" : "TESTS FAILED") << "\n";

        return all_passed ? 0 : 1;
    } catch (const std::exception& e) {
        std::cerr << "Fatal error: " << e.what() << "\n";
        return 2;
    }
}
```

---

## Compile command

```bash
nvcc -O3 -std=c++17 -arch=sm_70 reduction_sum.cu -o reduction_sum
```

If your GPU is older or newer, adjust `-arch`, for example:

```bash
nvcc -O3 -std=c++17 -arch=sm_80 reduction_sum.cu -o reduction_sum
```

---

## Run command

```bash
./reduction_sum
```

---

## Expected output format

Exact numeric values may vary slightly by GPU and compiler because floating-point summation is not associative.

Example format:

```text
[PASS] n = 0                        n=0          gpu=0                cpu=0                abs_err=0             tol=0
[PASS] n = 1                        n=1          gpu=42.5             cpu=42.5             abs_err=0             tol=0.000525
[PASS] small array                  n=5          gpu=15               cpu=15               abs_err=0             tol=0.00025
[PASS] negative values              n=5          gpu=-16.625          cpu=-16.625          abs_err=0             tol=0.00026625
[PASS] non-power-of-two             n=1003       gpu=...              cpu=...              abs_err=...           tol=...
[PASS] large random array           n=1048699    gpu=...              cpu=...              abs_err=...           tol=...
[PASS] mixed magnitudes             n=10007      gpu=...              cpu=...              abs_err=...           tol=...

Result: ALL TESTS PASSED
```

---

## Correctness and safety explanation

### Public API

```cpp
float gpu_reduce_sum(const float* host_input, size_t n)
```

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

```cpp
while (idx < n) {
    local_sum += input[idx];

    size_t second = idx + BLOCK_SIZE;
    if (second < n) {
        local_sum += input[second];
    }

    idx += stride;
}
```

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

```cpp
shared[tid] = local_sum;
__syncthreads();
```

This ensures all per-thread sums are visible before reduction begins.

Inside the shared-memory tree reduction:

```cpp
for (unsigned int offset = BLOCK_SIZE / 2; offset > 32; offset >>= 1) {
    if (tid < offset) {
        shared[tid] += shared[tid + offset];
    }
    __syncthreads();
}
```

Each iteration depends on values written by the previous iteration, so `__syncthreads()` is required and sufficient while multiple warps participate.

For the final warp, `__shfl_down_sync` is used. No block-wide synchronization is needed because only one warp participates.

There are no inter-block races because each block writes exactly one unique output element:

```cpp
output[blockIdx.x] = value;
```

---

## Performance notes

### Block size

The implementation uses:

```cpp
constexpr int kBlockSize = 256;
```

This is a common reduction block size because it gives:

- Enough threads per block for good occupancy.
- Moderate shared-memory usage.
- Efficient warp-level reduction.
- Two input elements per thread in the initial load pattern.

Each block processes up to `2 * BLOCK_SIZE` contiguous elements per grid-stride iteration.

---

### Memory coalescing

Within a block, threads read consecutive elements:

```cpp
input[idx]
input[idx + BLOCK_SIZE]
```

For a warp, these reads are contiguous, so global memory accesses are coalesced.

---

### Shared memory usage

Each block uses:

```cpp
BLOCK_SIZE * sizeof(float)
```

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

```text
(a + b) + c may differ from a + (b + c)
```

The GPU reduction tree sums values in a different order than the CPU reference implementation. Therefore, results may differ slightly.

The test harness compares against a double-precision CPU reference using a tolerance proportional to the sum of input magnitudes. This is especially important for mixed-magnitude inputs, where small values can be lost when added to very large values in single precision.
