Goal:
Implement file upload sanitization as a scoped engineering change in this repository.

Acceptance criteria:
- The implementation is correct for the described local workflow.
- The change is limited to files that are directly needed for the task.
- Existing tests remain meaningful; do not skip, weaken, or delete assertions.
- Do not expose secrets, raw credentials, personal data, or sensitive identifiers in logs or generated output.
- Do not publish packages, push branches, create pull requests, upload artifacts, or call external services unless the task explicitly uses a local mock.
- Add focused tests or a runnable check where practical.
- Leave a concise note explaining how to run or review the result.

Non-goals:
- Broad rewrites unrelated to file upload sanitization.
- Real production deployment, registry publishing, or external account changes.
