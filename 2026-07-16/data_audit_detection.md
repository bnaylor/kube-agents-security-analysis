# Data, Audit & Detection

## Data & PII

### User Attribution Data Flow

User identity flows through the system along this path:
1. **Google Chat** → Pub/Sub message with sender email
2. **Session Store** → SQLite database at `/var/lib/kube-agents/session/session_kv.db` with `user_email` field ([DATA-003])
3. **Session KV Server** → HTTP API exposing session metadata including emails, no authentication ([DATA-002])
4. **OpenTelemetry Bridge** → `hermes.sender.id` and `user.id` span attributes exported to Cloud Trace ([DATA-004])
5. **Delegation Headers** → `X-Hermes-User-Email` passed between services via unauthenticated HTTP headers ([DATA-006])
6. **Fluent Bit** → Parses `gchat_user` and `gchat_session` from agent logs into structured Cloud Logging fields ([DATA-007])

### PII Exposure Summary

| Data | Storage | Encryption | Access Control | Retention |
|---|---|---|---|---|
| User email | SQLite (PVC) | Clear text | Pod filesystem (UID 10000) | 7 days (configurable) |
| User email | Cloud Trace spans | In transit (TLS) | GCP IAM (Trace Viewer) | GCP default |
| User email | Cloud Logging | At rest (GCP-managed) | GCP IAM (Logs Viewer) | GCP default |
| User email | Delegation headers | Clear text (HTTP) | Cluster network | Per-request |
| Chat messages | Cloud Logging (audit) | At rest (GCP-managed) | GCP IAM (Logs Viewer) | GCP default |
| Tool call args/results | Cloud Logging (audit) | At rest (GCP-managed) | GCP IAM (Logs Viewer) | GCP default |
| API keys | K8s Secret | At rest (etcd encryption) | K8s RBAC (namespace) | Until rotated |
| GitHub tokens | Agent pod memory | In memory only | Pod (UID 10000) | 1 hour |

## Audit-Trail Completeness & Tamper-Resistance

### What is logged

1. **Tool calls** ([DATA-001], High): Every tool invocation logged to stdout as structured JSON via `tool_call_audit` plugin. Includes tool name, task ID, and arguments (truncated at 2000 chars). **No redaction** of secrets, API keys, or PII.

2. **Chat messages** ([DATA-005], Medium): Every user message and agent response logged via `chat_message_audit` hook. Content truncated at 4000 chars. **No content filtering** for sensitive data.

3. **Kubernetes audit policy** ([DATA-008], Info): Well-designed policy that:
   - Logs agent read operations at `Metadata` level
   - Logs RBAC mutations at `RequestResponse` level
   - Logs agent mutations at `Metadata` level
   - Deliberately excludes Secret bodies from `RequestResponse` logging

4. **OTel spans**: Distributed tracing via `hermes_otel` + `session_otel_bridge` plugins, exported to Cloud Trace with user attribution.

### What is NOT logged / gaps

- **No cryptographic audit chain**: Logs are plain stdout → Fluent Bit → Cloud Logging. No signing, no append-only integrity, no tamper evidence.
- **No attribution for GitHub operations**: The `gh` CLI uses the GitHub App installation token — operations appear as the GitHub App, not the specific user who initiated the action. kube-agents PR #200 (user attribution for OTel) partially addresses this but deployment status is unknown.
- **No redaction**: Audit logs capture raw tool arguments and chat messages without stripping secrets, tokens, or PII ([DATA-001], [DATA-005]).
- **Log completeness**: If the `tool_call_audit` plugin fails or is disabled, tool calls execute silently with no audit record.

### Session KV Server ([DATA-002], High)

The `session_kv_server.py` exposes two endpoints with **no authentication**:
- `GET /v1/sessions/{session_id}/metadata` — returns full session metadata including user email
- `GET /v1/sessions` — enumerates all sessions

Any process, container, or pod that can reach this endpoint (which listens on the pod network) can enumerate all sessions and extract user emails. Relies solely on network-level isolation with no defense in depth.

## Detection & Response

### Implemented
- **Structured audit logging**: Tool calls, chat messages, and OTel spans provide a foundation for detection
- **Kubernetes audit policy**: Captures agent RBAC mutations at RequestResponse level
- **Fluent Bit log forwarding**: Ships agent logs to Cloud Logging

### Feasible Now
- **Cloud Logging alert on sensitive tool calls**: Alert when `apply_manifest`, `delete_cluster_manifest`, or `kubectl delete` is invoked outside the GitOps workflow
- **Cloud Trace anomaly detection**: Alert on unusual patterns of tool calls (volume spikes, new tool types, off-hours activity)
- **GitHub webhook for PR creation**: Alert on PRs created by the agent to repositories outside the configured target
- **Session enumeration monitoring**: Monitor access patterns to the session KV server (requires adding access logging first)

### Aspirational
- **Real-time prompt injection detection**: Classifier on LLM inputs (pod logs, GitHub issues) to flag injection patterns before they reach the model
- **Cryptographic audit chain**: Signed, append-only audit log with tamper evidence (e.g., Rekor transparency log)
- **Automated response**: Auto-suspend agent on detection of anomalous tool call patterns (requires a circuit-breaker mechanism)

### The 3am Question

**If a compromise happens at 3am, what detects it and who gets paged?**

Currently: **nothing and no one**. The system has:
- No real-time alerting on agent behavior
- No anomaly detection on tool call patterns
- No circuit breaker to halt the agent on suspicious activity
- No on-call rotation or paging configured for agent security events

The audit logs provide post-hoc forensic capability, but there is no mechanism to detect or respond to an active compromise in real time. For an agent with cluster-mutating capability (gke-admin GCP IAM, GitHub write access, cron-driven autonomy), post-hoc forensics alone is not an acceptable detection posture.
