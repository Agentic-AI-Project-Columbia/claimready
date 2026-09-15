# Tasks

## 2026-09-15 Gemini model migration

- [x] Audit current model settings and provider lifecycle documentation.
- [x] Receive implementation and pull-request approval from Arjun.
- [x] Migrate the agent runtime to GA Gemini 3.5 Flash, separate Vertex location from Cloud Run region, and verify structured output and tool handoffs.
- [x] Run relevant tests and bounded provider smoke checks.
- [x] Review the diff and prepare the pull request.

### Review

The runtime and deployment manifest select retiring Gemini 2.5 Flash and couple the model endpoint to the Cloud Run region. Use GA Gemini 3.5 Flash, configure GCP_LOCATION independently with a global default, and update deployment overrides and tested adapter minimums. Preserve the current application flow and historical business-document estimates.

All 43 offline tests passed. Live streamed tool execution returned the expected structured result, and the actual extractor produced correct structured facts from a synthetic invoice without inventing registry identifiers. Lockfile, syntax, and diff checks passed.

Redeploy the backend after merge to apply AGENT_MODEL and global endpoint settings. Explicit VERTEXAI_LOCATION overrides must also support the chosen model.
