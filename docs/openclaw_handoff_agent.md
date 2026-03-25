# OpenClaw Installation Review and Remediation Handoff

## Purpose
Review Mauro's OpenClaw installation, verify how permissions, secrets, skills, and posting tools are currently wired, and fix the setup so the agent can operate safely.

This handoff is based on Mauro's reported behavior:
- He attempted to use OpenClaw to read his tweets.
- At least once, the system published comments from his account without his knowledge.
- The system selected websites and posted publicly.
- There was no clear trace of the command or approval event that caused the posting.
- He revoked the API keys afterward.

## Primary objective
Make the installation safe and understandable.

## Non-objectives
Do not optimize for maximum autonomy.
Do not create a "super container" with broad access.
Do not restore direct autonomous posting from within the agent container.

## Required mental model
Use this model consistently during review:
- **Host**: Mauro's real machine or server. This is where authority should live.
- **Gateway**: the control layer that reads config, routes tasks, and applies policy.
- **Container / sandbox**: the restricted environment where agent code or skills may run.
- **Skills**: usually stored on the host; execution may happen on host or in container depending on sandbox settings.
- **Node / router**: ignore unless the current installation truly uses them.

## Working principles
1. The agent should not directly hold broad write-capable credentials.
2. The container should stay minimal.
3. Irreversible actions must be separated from reasoning.
4. If posting to X is needed, authority should live outside the agent container.
5. Every public action must be attributable to a tool call, approval event, and log entry.

## Target architecture
### Safe pattern
- Agent runs inside a sandboxed container.
- Container has only the runtime it needs, for example Node.js and/or Python.
- Container may have read-only access to a narrow working directory.
- Container does **not** hold X posting credentials.
- Gateway enforces tool and execution boundaries.
- A separate host-side publisher service or script holds the X credentials.
- The publisher performs one narrow action only, such as `publish_tweet(text)` or, preferably, `create_draft(text)` and then `approve_and_publish(draft_id)`.
- Host-side publisher logs every invocation.

### Unsafe pattern to eliminate
- X keys stored in OpenClaw secrets in a way that makes them available to the agent or tool runtime.
- X posting tool callable directly from containerized agent code.
- Container with broad host mounts, broad internet access, and write-capable social credentials.
- No approval gate.
- No reliable audit trail.

## Questions to answer during review
1. Where exactly are the X credentials stored now?
   - OpenClaw dashboard secrets
   - host environment
   - container environment
   - Hostinger host
   - separate publisher service
2. Which component currently posts to X?
   - direct tool from agent
   - xurl inside container
   - xurl on host
   - custom script/service
3. Is sandboxing enabled?
4. If sandboxing is enabled, which secrets are injected into the sandbox?
5. Do skills run on host or in container in this installation?
6. Is host execution enabled?
7. Are exec approvals enabled and working?
8. Can one past public action be reconstructed from logs?

## Verification checklist
### A. Inventory current architecture
- Identify host, gateway, container, skills directory, and any external services.
- Record which runtimes are present in the container, for example Node.js and Python.
- Record mounted host paths.
- Record whether host execution is possible.
- Record whether nodes are configured. Ignore if absent.

### B. Inventory secrets
- Enumerate all secrets currently stored in OpenClaw.
- Classify each secret as one of:
  - safe in sandbox
  - safe only on host
  - should be removed
- Focus first on X/Twitter keys and any other write-capable credentials.

### C. Trace posting path
- Find every tool, command, or skill that can post to X.
- Determine whether xurl is executed on host or in container.
- Determine whether the posting path uses raw credentials directly from inside the sandbox.
- Confirm whether the agent can invoke posting without a separate approval boundary.

### D. Inspect logs and approvals
- Review OpenClaw logs, tool logs, and any host-side logs.
- Verify whether posting actions are visible in logs.
- Verify whether approval events are logged.
- If logs are missing or insufficient, document the gap as a defect.

### E. Skills review
- Confirm where skills are stored.
- Confirm where skills execute.
- Verify whether skills receive secrets automatically or explicitly.
- Verify whether any skill currently has access to X keys or shell execution that can reach posting tools.

## Required remediation
### 1. Remove direct posting authority from the container
- Remove X posting credentials from OpenClaw secrets if those secrets are accessible to the agent or tools in the sandbox.
- Remove any direct container path that can execute xurl with live X keys.

### 2. Move posting authority to host-side narrow service
Create or validate a host-side publisher with these constraints:
- Holds the X credentials.
- Exposes one narrow action only.
- Logs every request.
- Rejects unexpected parameters.
- Supports explicit approval before final publish, if possible.

Preferred API shape:
- `create_draft(text)`
- `approve_and_publish(draft_id)`

Minimum acceptable API shape:
- `publish_tweet(text)`

### 3. Keep the container minimal
The container should include only what it needs to reason and draft:
- required runtime only, for example Node.js and/or Python
- required libraries only
- narrow working directory mount only

The container should not include:
- X posting credentials
- broad host filesystem access
- arbitrary host execution unless there is a specific reviewed need

### 4. Enforce an approval boundary
At minimum, one of these must exist:
- manual approval before publish
- draft creation only, with publish performed separately
- host-side publisher that refuses direct public posting without explicit confirmation token

### 5. Improve observability
Ensure every publish-capable flow records:
- initiating prompt or request
- tool invocation
- exact text sent for publishing
- approval event
- final publish result
- timestamp

## Acceptance criteria
The installation is acceptable only if all of the following are true:
1. The agent container cannot directly access X posting credentials.
2. xurl or equivalent publish command runs on host or in a separate narrow service, not in the agent container.
3. Public posting is separated from drafting.
4. A single past or test publish action can be traced end-to-end in logs.
5. The container has only minimal mounts and minimal secrets.
6. Mauro can understand, in one sentence, where code runs and what it can touch.

## Explicit guidance on runtimes
- Node.js is the JavaScript runtime.
- Python is required only if some installed tools or skills need Python.
- Runtime presence is not the main risk.
- The main risk is broad permissions plus write-capable secrets.

## Concrete instructions for this review
1. Do not start by adding more tools or more secrets.
2. First map the current architecture.
3. Then remove direct social posting authority from the sandbox.
4. Then rebuild the publish path outside the container.
5. Then test with a safe dry run or draft-only mode.
6. Only after that consider reintroducing controlled public posting.

## Deliverables expected from the reviewing agent
Provide Mauro with:
1. A short architecture map of the current installation.
2. A list of all secrets relevant to posting, and where they currently live.
3. A list of all paths by which the agent can currently publish.
4. The specific changes made.
5. The final safe publish path.
6. Any remaining risks.
7. A short plain-language explanation of host, gateway, container, sandbox, skills, and where authority now lives.

## Final rule
The agent should generate intent. Authority should live elsewhere.
