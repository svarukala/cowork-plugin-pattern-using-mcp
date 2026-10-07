---
title: Build a reusable MCP plugin for Microsoft Copilot Cowork
description: Connect Cowork to a line-of-business API through an Entra-protected MCP endpoint and secretless Microsoft Entra SSO.
ms.date: 10/06/2026
ms.topic: overview
---

# Build a reusable MCP plugin for Microsoft Copilot Cowork

Give Microsoft Copilot Cowork access to a line-of-business (LOB) API without putting credentials in a plugin package. This pattern combines a Microsoft 365 app package, an Entra-protected MCP endpoint published through Azure API Management (APIM), and a private Model Context Protocol (MCP) adapter. The worked example hosts the adapter on Azure Container Apps.

Cowork authenticates users through **Microsoft Entra SSO client ID registration** in the Microsoft Enterprise token store. You don't create a client secret for this connection. If the LOB API requires an API key, the adapter retrieves that separate credential from Azure Key Vault using managed identity.

This article set uses a fictional **Contoso Catalog** LOB API. Substitute your own service contract and organization. It targets a single organization in Azure public cloud and read-only, bounded operations. Any signed-in user in that organization who consents can use the connector; to narrow access, see [Limit who can use the connector](configure-secretless-sso.md#optional-limit-who-can-use-the-connector).

## When to use this pattern

Cowork connectors currently authenticate with `OAuthPluginVault` (Entra SSO or OAuth), dynamic client registration, or no authentication. [API-key authentication isn't available in Cowork yet](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development). A backend that only accepts an API key therefore needs an Entra-protected MCP facade that Cowork can call with a user token.

| Existing LOB backend | Recommended shape |
| --- | --- |
| **REST API secured with an API key** | APIM exposes an Entra-protected `/mcp` endpoint. A custom MCP adapter (this worked example) or [APIM's native REST-to-MCP](https://learn.microsoft.com/en-us/azure/api-management/export-rest-mcp-server) calls the API with a key from Key Vault. |
| **REST API secured with Entra** | Same front end. The backend call uses an application identity (managed identity), or an explicit [on-behalf-of](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow) exchange when the API must see the user. |
| **MCP server secured with an API key** | Keep the server. Put an Entra-protected gateway, such as [APIM's MCP proxy](https://learn.microsoft.com/en-us/azure/api-management/expose-existing-mcp-server), in front and inject the key at the backend. No custom adapter is needed. |
| **MCP server secured with Entra** | APIM is optional. Connect directly when Cowork can reach the server and it validates tokens for the SSO resource application. Add APIM for central policy, rate limits, or private-network publishing. |

In every case, the URL in the plugin's `agentConnectors[].toolSource.remoteMcpServer.mcpServerUrl` is the Entra-protected MCP endpoint, never the LOB API itself. In the worked example, APIM publishes that endpoint as a facade over the private adapter.

> [!IMPORTANT]
> This is an implementation pattern, not a Microsoft product release or a one-command deployment kit. The examples are locally checked integration examples; they aren't a complete hosted service or infrastructure deployment. Authentication middleware, the real upstream adapter, infrastructure, branding, and tenant acceptance remain implementation tasks. See [validation-report.json](validation-report.json) for the offline checks that were run.

## Follow the article set

| Article | Outcome |
| --- | --- |
| [Configure secretless Entra SSO](configure-secretless-sso.md) | Register the resource app and token-store auth configuration; align scopes and audiences. |
| [Build and deploy the adapter](build-and-deploy.md) | Implement bounded MCP tools and deploy the private adapter behind an authenticated gateway. |
| [Package the Cowork plugin](package-and-validate.md) | Generate real tool definitions, assemble the package, publish it, and perform acceptance checks. |
| [Operate and troubleshoot](operate-and-troubleshoot.md) | Diagnose identity, networking, backend, and package failures without weakening controls. |

## Architecture

The public entry point is `https://<gateway-host>/mcp`. Cowork never connects directly to the adapter or receives the backend API key.

| Component | Responsibility | Trust boundary |
| --- | --- | --- |
| Cowork app package | Declares the connector URL, token-store registration reference, and tool definitions; optionally includes a skill. | Contains identifiers, not credentials. |
| Microsoft Enterprise token store and Entra ID | Obtain delegated tokens for the signed-in user using the SSO registration. | User sign-in, consent, and tenant policy. |
| Public APIM gateway | Exposes the Entra-protected MCP endpoint; validates tenant, audience, client, and delegated scope; applies rate limits; forwards MCP transport without buffering. | Only tokens issued to the token-store client for this API reach the adapter. |
| Private adapter host | Runs the Python MCP adapter and accepts traffic only from APIM. The example uses an internal Azure Container Apps environment; Azure App Service, AKS, or another private host also works. | No public backend bypass. |
| Adapter authentication and tools | Revalidates the token; maps the delegated scope to tool permissions; validates inputs and bounded results. | Model instructions and tool annotations aren't authorization. |
| User-assigned managed identity and Key Vault | Retrieve the backend credential at runtime. | A separate service-to-service identity, not the Cowork SSO client. |
| LOB API | Supplies the requested record or bounded result window. | Receives its own API key, never the user's Entra token. |
| Registry and monitoring | Deliver versioned images and record sanitized health, latency, and error information. | No tokens, secret values, or payload capture in logs. |

![Cowork uses secretless Entra SSO to call a public gateway; a private MCP adapter returns bounded results and optionally retrieves a backend key with managed identity.](diagrams/cowork-mcp-data-flow.svg)

*Client SSO and backend authentication are separate trust boundaries. Blue arrows show requests, green arrows show results, and purple dashed arrows show identity/dependency paths. This is a target design, not an observed packet capture.*

> [!NOTE]
> Every user in the organization who can sign in and consent can call the tool. When the adapter calls the LOB API with its own credential, they all receive the same backend access. That suits read-only, nonsensitive data. If results must differ per user, enforce that in the adapter or use on-behalf-of so the LOB API makes its own decisions.

[Full-size PNG](diagrams/cowork-mcp-data-flow.png) | [Editable Excalidraw source](diagrams/cowork-mcp-data-flow.excalidraw) | [Network diagram](diagrams/cowork-mcp-network.svg)

### Request flow

1. Cowork reads the connector's `OAuthPluginVault` registration reference.
2. Microsoft 365 uses the corresponding SSO auth configuration to obtain a delegated Entra access token. Sign-in or consent can still be required.
3. Cowork sends an MCP request with the bearer token to the public gateway.
4. APIM checks the signature, tenant, intended resource, Microsoft token-store client, and delegated scope.
5. APIM forwards the request and token to the private adapter over HTTPS. The adapter performs independent token validation and tool authorization.
6. The adapter retrieves the backend key through its managed identity and invokes one allowlisted LOB API operation with bounded time and output.
7. The adapter returns an MCP result, or an explicit error. Cowork must not interpret an error as an empty result set.

### Choose custom adaptation or native APIM MCP

Use this **custom-adapter pattern** when you need application-specific result validation, output shaping, tool-level authorization, or orchestration that goes beyond a simple REST operation mapping.

If selected REST operations already have suitable input/output contracts, consider [APIM's native REST-to-MCP capability](https://learn.microsoft.com/en-us/azure/api-management/export-rest-mcp-server). For an existing compatible MCP service, consider [APIM's native MCP proxy](https://learn.microsoft.com/en-us/azure/api-management/expose-existing-mcp-server).

Those alternatives aren't the same deployment. The reviewed custom adapter uses a regular APIM HTTP API to forward `/mcp`; the related toolkit generates native MCP resources. Native routes commonly end in `/<api-id>/mcp`. Don't copy a native route into this pattern without changing the connector, SSO Base URL, metadata, and gateway routing together.

## Prerequisites

Have the following before deployment:

- Access to Copilot Cowork and a test tenant that permits custom app installation. Confirm current licensing, availability, and organizational policy.
- An Azure subscription, approved region/cost envelope, and permissions to deploy the selected resources. Role assignment creation needs separate RBAC authority.
- Entra permission to register or manage the resource app, expose delegated scopes, configure preauthorization, and grant consent. Azure subscription ownership doesn't automatically grant Entra directory privileges.
- An API contract, permission to call the LOB API, an appropriate test record, and an approved credential-handling process if the API uses an API key.
- Python 3.12+, PowerShell 7 for the Windows examples, Azure CLI/Bicep, and a Linux-container build environment. Install Microsoft 365 Agents Toolkit CLI for package validation and personal installation.
- A plan for private DNS, APIM-to-backend connectivity, Key Vault connectivity, image pulls, monitoring, and outbound access from APIM and the adapter to Microsoft Entra (token signing keys) and the LOB API.
- Your own publisher name, working HTTPS website/privacy/terms URLs, and app icons.

APIM Developer is billable and intended for development, not a production availability commitment. The Consumption tier doesn't support the `rate-limit-by-key` policy used in the example. Don't assume the same SKU/network topology works in every region or tier.

## Pattern boundaries

The adapter makes independent, bounded calls to the LOB API. Confirm the API's concurrency and quota contract; APIM rate limits are admission controls, not exact upstream quota enforcement.

Exports, write operations, automatic pagination, arbitrary destination URLs, and automatic retries aren't part of the baseline. Add them only with their own permissions, contracts, and acceptance criteria.

## Related content

- [Build plugins for Copilot Cowork](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development)
- [Configure Microsoft Entra SSO authentication](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-authentication-entra-sso)
- [Configure plugin authentication](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-authentication)
- [Azure Container Apps networking](https://learn.microsoft.com/en-us/azure/container-apps/networking)
