## `reduction_shared.cu`

```cuda
#include <cuda_runtime.h>

#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#define CUDA_CHECK(call)                                                     \
    do {                                                                     \
        cudaError_t err__ = (call);                                           \
        if (err__ != cudaSuccess) {                                           \
            std::ostringstream oss__;                                         \
            oss__ << "CUDA error at " << __FILE__ << ":" << __LINE__          \
                  << " for " << #call << ": " << cudaGetErrorString(err__);  \
            throw std::runtime_error(oss__.str());                           \
        }                                                                    \
    } while (0)

constexpr unsigned int BLOCK_SIZE = 256;

static size_t divUp(size_t a, size_t b) {
    return a == 0 ? 0 : 1 + (a - 1) / b;
}

class DeviceFloatBuffer {
public:
    DeviceFloatBuffer() = default;

    explicit DeviceFloatBuffer(size_t count) {
        allocate(count);
    }

    ~DeviceFloatBuffer() {
        if (ptr_) {
            cudaFree(ptr_);
        }
    }

    DeviceFloatBuffer(const DeviceFloatBuffer&) = delete;
    DeviceFloatBuffer& operator=(const DeviceFloatBuffer&) = delete;

    void allocate(size_t count) {
        if (count == 0) {
            return;
        }
        CUDA_CHECK(cudaMalloc(reinterpret_cast<void**>(&ptr_), count * sizeof(float)));
    }

    float* get() const {
        return ptr_;
    }

private:
    float* ptr_ = nullptr;
};

__global__ void reduceSumKernel(const float* __restrict__ input,
                                float* __restrict__ output,
                                size_t n) {
    extern __shared__ float sdata[];

    unsigned int tid = threadIdx.x;

    // Each block reduces up to 2 * blockDim.x input elements.
    size_t base = static_cast<size_t>(blockIdx.x) * blockDim.x * 2 + tid;

    float threadSum = 0.0f;

    if (base < n) {
        threadSum += input[base];
    }

    size_t second = base + blockDim.x;
    if (second < n) {
        threadSum += input[second];
    }

    sdata[tid] = threadSum;
    __syncthreads();

    // Shared-memory tree reduction.
    // BLOCK_SIZE is a power of two, and shared memory has BLOCK_SIZE floats.
    for (unsigned int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (tid < stride) {
            sdata[tid] += sdata[tid + stride];
        }
        __syncthreads();
    }

    if (tid == 0) {
        output[blockIdx.x] = sdata[0];
    }
}

static void launchReductionKernel(const float* d_input,
                                  float* d_output,
                                  size_t n,
                                  size_t numBlocks) {
    if (numBlocks == 0) {
        return;
    }

    if (numBlocks > static_cast<size_t>(std::numeric_limits<unsigned int>::max())) {
        throw std::runtime_error("Too many CUDA blocks requested for this example.");
    }

    reduceSumKernel<<<static_cast<unsigned int>(numBlocks),
                      BLOCK_SIZE,
                      BLOCK_SIZE * sizeof(float)>>>(d_input, d_output, n);

    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());
}

static float gpuReduceSum(const std::vector<float>& h_input) {
    const size_t n = h_input.size();

    if (n == 0) {
        return 0.0f;
    }

    DeviceFloatBuffer d_input(n);
    CUDA_CHECK(cudaMemcpy(d_input.get(),
                          h_input.data(),
                          n * sizeof(float),
                          cudaMemcpyHostToDevice));

    // First pass: each block consumes up to 2 * BLOCK_SIZE elements.
    size_t numBlocks = divUp(n, static_cast<size_t>(BLOCK_SIZE) * 2);

    DeviceFloatBuffer d_partialA(numBlocks);
    DeviceFloatBuffer d_partialB(numBlocks > 1 ? numBlocks : 0);

    launchReductionKernel(d_input.get(), d_partialA.get(), n, numBlocks);

    float* d_current = d_partialA.get();
    float* d_next = d_partialB.get();
    size_t currentCount = numBlocks;

    // Repeatedly reduce partial sums on the GPU until one value remains.
    while (currentCount > 1) {
        size_t nextBlocks = divUp(currentCount, static_cast<size_t>(BLOCK_SIZE) * 2);

        launchReductionKernel(d_current, d_next, currentCount, nextBlocks);

        std::swap(d_current, d_next);
        currentCount = nextBlocks;
    }

    float result = 0.0f;
    CUDA_CHECK(cudaMemcpy(&result, d_current, sizeof(float), cudaMemcpyDeviceToHost));

    return result;
}

struct CpuReferenceResult {
    double sum;
    double absSum;
};

static CpuReferenceResult cpuReferenceSum(const std::vector<float>& input) {
    CpuReferenceResult result{0.0, 0.0};

    for (float x : input) {
        double dx = static_cast<double>(x);
        result.sum += dx;
        result.absSum += std::fabs(dx);
    }

    return result;
}

static std::vector<float> makePattern(size_t n, bool allowNegative) {
    std::vector<float> data(n);

    for (size_t i = 0; i < n; ++i) {
        if (allowNegative) {
            // Values in roughly [-1.28, 1.28].
            int v = static_cast<int>(i % 257) - 128;
            data[i] = static_cast<float>(v) * 0.01f;
        } else {
            // Positive values in [0.001, 0.101].
            data[i] = static_cast<float>((i % 101) + 1) * 0.001f;
        }
    }

    return data;
}

static bool runTest(const std::string& name, const std::vector<float>& input) {
    CpuReferenceResult cpu = cpuReferenceSum(input);
    float gpu = gpuReduceSum(input);

    double diff = std::fabs(static_cast<double>(gpu) - cpu.sum);

    // Float reductions are order-dependent.  This tolerance scales with the
    // magnitude of the data while remaining strict for small arrays.
    double tolerance = 1.0e-5 * cpu.absSum + 1.0e-4;

    bool pass = diff <= tolerance;

    std::cout << std::left << std::setw(32) << name
              << " n=" << std::setw(10) << input.size()
              << " CPU=" << std::setw(16) << std::setprecision(9) << cpu.sum
              << " GPU=" << std::setw(16) << std::setprecision(9) << gpu
              << " diff=" << std::setw(14) << std::setprecision(9) << diff
              << " tol=" << std::setw(14) << std::setprecision(9) << tolerance
              << (pass ? " PASS" : " FAIL")
              << '\n';

    return pass;
}

int main() {
    try {
        bool allPassed = true;

        // Test case 1: small array.
        allPassed &= runTest("Small array",
                             std::vector<float>{1.0f, 2.0f, 3.0f, 4.0f, 5.0f, 6.0f, 7.0f});

        // Test case 2: one element.
        allPassed &= runTest("One element",
                             std::vector<float>{123.456f});

        // Test case 3: non-power-of-two length.
        allPassed &= runTest("Non-power-of-two length",
                             makePattern(12345, false));

        // Test case 4: large array.
        allPassed &= runTest("Large array",
                             makePattern((1u << 22) + 123, false));

        // Test case 5: array containing negative values.
        allPassed &= runTest("Negative values",
                             makePattern(7777, true));

        CUDA_CHECK(cudaDeviceReset());

        if (!allPassed) {
            std::cerr << "At least one test failed.\n";
            return EXIT_FAILURE;
        }

        std::cout << "All tests passed.\n";
        return EXIT_SUCCESS;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return EXIT_FAILURE;
    }
}
```

## Compile

```bash
nvcc -O3 -std=c++14 reduction_shared.cu -o reduction_shared
```

Optionally specify your GPU architecture, for example:

```bash
nvcc -O3 -std=c++14 -arch=sm_70 reduction_shared.cu -o reduction_shared
```

## Run

```bash
./reduction_shared
```

## Explanation

- `BLOCK_SIZE` is `256`, a power of two, which simplifies the shared-memory tree reduction.
- Each thread initially loads up to two global-memory elements:
  - `input[base]`
  - `input[base + blockDim.x]`
- Therefore each block reduces up to `2 * BLOCK_SIZE`, or `512`, input elements.
- The grid size is computed as:

```cpp
numBlocks = ceil(n / (2 * BLOCK_SIZE))
```

so the code does not require `n` to be divisible by the block size or to be a power of two.

Bounds checks are used before every global-memory read:

```cpp
if (base < n) ...
if (second < n) ...
```

Shared memory is allocated with exactly `BLOCK_SIZE` floats, and the reduction loop only accesses valid indices from `0` to `BLOCK_SIZE - 1`.

Partial block results are written to a temporary device array. If more than one partial result remains, the same reduction kernel is launched again on the partial sums. This repeats until only one value remains, which is copied back to the host and compared against a CPU reference sum using a floating-point tolerance.
