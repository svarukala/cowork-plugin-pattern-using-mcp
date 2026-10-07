---
title: Operate and troubleshoot a Cowork MCP plugin
description: Diagnose Cowork SSO, gateway, private adapter, and packaging failures with explicit evidence and safe operational boundaries.
ms.date: 10/06/2026
ms.topic: troubleshooting
---

# Operate and troubleshoot a Cowork MCP plugin

Distinguish package validation, transport connectivity, user authorization, and business-operation success. HTTP 200 can carry an MCP error. A healthy revision or public metadata response doesn't demonstrate a successful tool call.

## Diagnose by boundary

| Symptom | Check | Corrective action |
| --- | --- | --- |
| Registration form requires your own client secret | Registration type in Teams developer portal. | Use **Microsoft Entra SSO client ID registration**, not generic OAuth registration. Don't invent a workaround. |
| Entra reports invalid resource/scope | SSO Application ID URI in `identifierUris`; enabled scope; portal scope value. | Bind the exact returned URI to the same resource app; preserve existing entries. |
| Repeated consent/sign-in prompt | SSO Web callback; token-store preauthorization for the intended scope; organization/app restriction; tenant consent policy. | Correct the mismatched setting with administrator approval. Don't substitute the generic OAuth callback. |
| First call works, later calls require sign-in | `offline_access` in the registration Scope field and Conditional Access/session policy. | Test renewal separately. Refresh support doesn't override tenant reauthentication policy. |
| HTTP 401 from gateway | Tenant, audience, v2 issuer/version, token-store client, delegated scope. | Compare expected values using sanitized verifier diagnostics. Don't log or paste raw tokens. |
| Every request fails with 401 or 500, even valid tokens | Outbound access from APIM or the adapter to `login.microsoftonline.com` for discovery and signing keys. | Allow that destination through your NAT gateway, firewall, or routes. Don't disable signature validation. |
| Valid-looking URI but audience check fails | `aud` for the actual token version. | Entra v2 uses the resource app client ID; configure it along with the same-resource SSO alias. Never accept unrelated resources. |
| Admin/CLI probe fails but Cowork works | Client application restriction. | A CLI client isn't the token-store client. Keep the restriction; use proper test fixtures and Cowork acceptance. |
| A user can't sign in to the connector | If **Assignment required** is on, the user's or group's assignment; otherwise consent and Conditional Access. | Assign the user or group in the enterprise application, or grant the required consent. |
| HTTP 502 or unready backend | Private DNS, APIM subnet connectivity, adapter host ingress, port 8000, image pull, signing-key access. | Fix the actual dependency. Don't expose the backend publicly or disable verification. |
| Key Vault credential unavailable | Managed identity selection, secret-scoped RBAC, private DNS/reachability, enabled/valid secret version. | Correct the grant or approved secret state; allow for RBAC propagation. Don't place the key in app settings. |
| HTTP 429 | Gateway quota versus LOB API quota. | Respect retry guidance and reduce demand. Per-user gateway limits don't enforce all consumers of a shared backend credential. |
| HTTP 200 with `isError: true` | MCP error category and correlation ID. | Report the failure. Don't interpret it as "no records". |
| MCP stream fails with diagnostics enabled | Inherited response logging or policies accessing `context.Response.Body`. | Keep response payload capture off and avoid buffering transformations. |
| Package upload rejects a field | Exact v1.28 schema, capitalization, and nesting. | Use `authorization.referenceId`, direct `mcpToolDescription.file`, and supported root fields. |
| Tool appears but arguments fail | Tool-description file versus deployed SDK schema. | Regenerate from the exact implementation; preserve parameter nesting and publish the updated package. |
| Read-only tool asks the user for confirmation | Tool `annotations` returned by live `tools/list`. | Set `readOnlyHint: true`, `destructiveHint: false`, and a `title`. Unannotated tools are treated as destructive. |
| Plugin doesn't appear | Correct signed-in account, install scope, app policy, Cowork availability, and **Shared with me** versus **Discover**. | Complete the supported installation/approval path; don't assume a local ZIP is installed. |

> **Image placeholder - Correlate a failure without payload capture**  
> Intended screenshot: A sanitized monitoring view containing time, request correlation ID, latency, status, and error category, with no request/response bodies or authorization headers.  
> Alt text: "Sanitized MCP diagnostics correlate a request with a gateway or backend error category."  
> Caption: "Diagnose the failing boundary without recording credentials or business payloads."

## Monitor and recover

Track gateway authorization failures and throttling, tool error categories, latency, readiness failures, revision changes, and upstream availability. Restrict monitoring access and retention. Disable SDK HTTP debug logging and request/response header/body capture unless a separately reviewed redaction design proves it safe.

On dependency failure, fail closed and report the boundary that failed. Don't fall back to anonymous mode, a different client identity, cached business results, or another API without an explicit product design.

Before restarting or rolling back, capture nonsecret deployment state. A restart can't repair a wrong SSO URI, a missing consent, or a broken private DNS record. Restore only the solution's known-good image/configuration/policy after reviewing compatibility.

## Change credentials and permissions deliberately

Backend API-key rotation is independent of Cowork SSO registration. Use an approved Key Vault rotation process, validate the intended new version with the backend, and confirm behavior before retiring the previous credential. Never paste the key into commands or package files.

User access needs no gateway or adapter change. If you enabled **Assignment required**, onboard and offboard through the assigned Entra group. Review token lifetime and revocation behavior; an existing access token may remain valid until its expiry unless your resource implements the applicable revocation/claims-challenge behavior.

Changing endpoint, scope, resource app, or package identity can affect the token-store registration and installed clients. Update the connector, Base URL, metadata, policy, backend verifier, and tool definitions as a coordinated release.

## Retire the solution safely

Inventory the installed app, token-store registration, Entra application/service principal, Azure resources, image artifacts, and role grants. Resource-group deletion doesn't remove tenant-scoped registrations or installed apps.

Obtain explicit approval before uninstallation or deletion. Preserve shared APIM resources, platform-managed infrastructure, unrelated vaults/storage, and required audit records. Review Key Vault soft-delete/purge protection and ongoing Azure charges; disabling a plugin doesn't stop billing.

## Authoritative references

- [Configure Microsoft Entra SSO](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-authentication-entra-sso)
- [Entra access-token claims](https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference)
- [Validate Microsoft Entra tokens in APIM](https://learn.microsoft.com/en-us/azure/api-management/validate-azure-ad-token-policy)
- [Expose and govern an existing MCP server](https://learn.microsoft.com/en-us/azure/api-management/expose-existing-mcp-server)
- [Secure MCP servers in APIM](https://learn.microsoft.com/en-us/azure/api-management/secure-mcp-servers)
- [Container Apps networking](https://learn.microsoft.com/en-us/azure/container-apps/networking)
- [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development)
