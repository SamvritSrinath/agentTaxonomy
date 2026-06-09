Here is a complete, production-quality CUDA C++ reduction primitive for summing large float arrays. It is designed to be correct, maintainable, and highly performant, with robust error handling and validation tests.

---

### 1. Complete Source Code (`reduction.cu`)
---

### 2. Compile Command

Compile the code using `nvcc` with optimizations enabled:
*(Note: You can replace `-arch=sm_70` with your specific GPU architecture, e.g., `sm_75`, `sm_80`, `sm_86`, or `sm_90`.)*

---

### 3. Expected Output Format

```text
--------------------------------------------------
Running Test: Empty Array (n =
