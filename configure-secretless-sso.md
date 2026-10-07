---
title: Configure secretless Entra SSO for a Cowork MCP connector
description: Register a resource application and Enterprise token-store SSO configuration without creating a client secret.
ms.date: 10/06/2026
ms.topic: how-to
---

# Configure secretless Entra SSO for a Cowork MCP connector

Use the Microsoft-supported **Microsoft Entra SSO client ID registration** workflow. This creates an authentication configuration in the Microsoft Enterprise token store. Cowork references that record when obtaining tokens for your API.

[Microsoft's SSO documentation](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/plugin-authentication-entra-sso) supports three ways to create the auth configuration:

| Tool | What it does |
| --- | --- |
| Microsoft 365 Agents Toolkit | Creates the auth configuration from your project and writes the returned ID into the manifest. |
| `declarative-agent-developer` skill in Microsoft Work IQ | Same outcome from an agent-assisted workflow. |
| Teams developer portal | Manual form that shows every value explicitly. This article uses it so each identifier is visible. |

Registrations created by the tools are stored in the same token store and can be viewed and managed afterward in Teams developer portal. No tool removes the resource-app updates in [section 4](#4-complete-the-resource-app-binding) and the audience checks in [section 5](#5-align-audiences-and-authorization).

> [!IMPORTANT]
> Do not select generic OAuth client registration and create a client secret. Do not substitute dynamic client registration, PKCE, a managed identity, or a federated credential for this product-specific SSO registration. `OAuthPluginVault` alone doesn't identify which authentication flow a registration uses.

## 1. Keep the identifiers distinct

Use this mapping in your nonsecret deployment configuration.

| Identifier | Meaning | Used by |
| --- | --- | --- |
| `TENANT_ID` | Your Entra directory ID. | Tenant-specific issuer and token validation. |
| `API_CLIENT_ID` | Application/client ID of the resource app that secures your MCP endpoint. | SSO Client ID field; v2 access-token `aud`. |
| Application object ID | Directory object for that application. | Application administration, not token audience. |
| Resource service-principal object ID | Enterprise application in your tenant. | Consent and optional user/group assignment. |
| `SSO_REGISTRATION_ID` | Auth config ID returned by the token store; currently labeled Microsoft Entra SSO registration ID. | Cowork `authorization.referenceId`. |
| `SSO_APPLICATION_ID_URI` | Exact Application ID URI returned by that registration. | Additional resource identifier and resource audience configuration. |
| `M365_APP_ID` | Stable GUID at the root of the app package manifest. | Package identity and app restriction in the portal. |
| `MANAGED_IDENTITY_CLIENT_ID` | Adapter's Azure user-assigned identity. | Key Vault and image-pull access; never the SSO Client ID field. |

The Microsoft Enterprise token-store client ID is **`ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b`**. This is a Microsoft-published constant, not a value to generate for your deployment.

## 2. Register the resource application

1. Open **Microsoft Entra admin center > App registrations > New registration**.
2. Create a single-tenant resource app, such as **Contoso Catalog MCP**. Record its Application (client) ID, Object ID, and tenant ID.
3. Under **Expose an API**, configure an initial Application ID URI, such as `api://<API_CLIENT_ID>`. Add an enabled delegated scope named **`catalog.read`**, with display text such as *Read Contoso Catalog records*. Choose whether users can consent or only administrators can, according to your tenant consent policy.
4. For this new resource app, set `api.requestedAccessTokenVersion` to `2` in its manifest. Don't change an existing shared API's token version without compatibility review.
5. Confirm that the associated enterprise application (service principal) exists. If administration tooling created only the application object, create the service principal using supported Entra/Graph administration.

The delegated scope lets the token store call your API on behalf of the signed-in user. It's separate from the Azure RBAC roles of your managed identity. Don't grant application permissions to avoid a consent error.

The registration is single-tenant because the connector, the LOB API, and its data belong to one organization. Learn's guidance to allow **Any Microsoft 365 organization** applies to plugins distributed across tenants, which need a multitenant resource app, per-tenant consent, and tenant-aware token validation. That's a different design.

### Optional: Limit who can use the connector

By default, any user in your organization who signs in and consents can call the tool. To limit access to specific people, use Entra alone; no gateway or code change is needed:

1. Open the enterprise application and set **Assignment required?** to **Yes**.
2. Under **Users and groups**, assign the intended users or groups.

Entra then refuses to issue tokens to unassigned users, so they never reach APIM. Manage membership through the group, not through lists in policy or configuration.

## 3. Create the token-store SSO registration

1. Open [Teams developer portal](https://dev.teams.microsoft.com/tools).
2. Select **Tools > Microsoft Entra SSO client ID registration**.
3. Select **Register client ID**, or **New client registration** if registrations already exist.
4. Complete the fields:

| Portal field | Value for this pattern |
| --- | --- |
| Registration name | A recognizable name, such as **Contoso Catalog MCP SSO**. |
| Base URL | The exact connector endpoint: `https://<gateway-host>/mcp`. Use the gateway, not the private Container App. |
| Restrict usage by org | Your intended Microsoft 365 organization. This is an internal, single-tenant pattern. |
| Restrict usage by app | Restrict to your final app ID when available. If not known, use **Any Teams app** temporarily, then bind the published app ID. |
| Client ID | `API_CLIENT_ID` from the resource application. |
| Scope | The enabled API scope `catalog.read`; include `offline_access` alongside it when automatic token refresh is required. |

Use the scope values required by your resource app. For this example the portal field is `catalog.read offline_access` when refresh is needed. The full resource scope is `<SSO_APPLICATION_ID_URI>/catalog.read`. The token's `scp` permission check remains the short value `catalog.read`, not the full URI and not `offline_access`.

> [!NOTE]
> Published walkthroughs use both forms in the Scope field. The [Copilot Camp SSO lab](https://microsoft.github.io/copilot-camp/pages/copilot-cowork/03-cowork-plugins-sso/) enters the full `<Application ID URI>/<scope>` after the registration returns its URI; the reference implementation for this pattern works with the short value. If sign-in reports an invalid scope, switch to the full URI form.

> **Image placeholder - Select the secretless registration type**  
> Intended screenshot: Teams developer portal Tools page highlighting **Microsoft Entra SSO client ID registration**, not generic OAuth registration. Use a clean test tenant.  
> Alt text: "Microsoft Entra SSO client ID registration selected in Teams developer portal."  
> Caption: "Select the SSO-specific registration; this workflow doesn't require your own client secret."

> **Image placeholder - Complete SSO registration fields**  
> Intended screenshot: The SSO registration form with a fictional gateway Base URL, resource Client ID, `catalog.read offline_access`, and organization/app restrictions. Redact real organization, user, and application identifiers.  
> Alt text: "SSO registration form with the public MCP URL, API client ID, delegated scope, and restricted organization access."  
> Caption: "Bind the registration to the same resource and endpoint that the connector uses."

5. Select **Save**. Copy the returned **Microsoft Entra SSO registration ID** and **Application ID URI** exactly into your nonsecret deployment record.

Don't synthesize these values, infer the registration ID from the URI, or copy another connector's values. Don't automate an undocumented portal API.

> **Image placeholder - Capture the returned identifiers**  
> Intended screenshot: The saved registration showing the two distinct fields, labeled with illustrative redactions rather than invented successful values.  
> Alt text: "Saved SSO registration showing separate registration ID and Application ID URI fields."  
> Caption: "The registration ID goes into the package; the Application ID URI goes into the resource app and validation configuration."

## 4. Complete the resource-app binding

Return to the resource application in Entra:

1. Add `SSO_APPLICATION_ID_URI` to `identifierUris`. Preserve the initial URI and any existing valid entries. The portal can display only the first URI; use the manifest editor for multiple entries.
2. Under **Authentication**, add this exact redirect URI under the **Web** platform:

   ```text
   https://teams.microsoft.com/api/platform/v1.0/oAuthConsentRedirect
   ```

3. Under **Expose an API > Authorized client applications > Add a client application**, enter `ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b`.
4. Select the enabled **catalog.read** scope. In the application manifest, its scope GUID belongs in this client's `delegatedPermissionIds`. Don't use the textual scope value where a scope GUID is required.
5. Preserve existing scopes, preauthorizations, web settings, and roles. Obtain administrator approval/consent as required by your tenant; preauthorization doesn't bypass assignment or Conditional Access.

> **Image placeholder - Finish resource-app configuration**  
> Intended composite screenshot: Manifest `identifierUris` with the additional SSO URI, Web redirect URI, and authorized Microsoft token-store client with the checked scope. Redact deployment-specific IDs.  
> Alt text: "Resource app configured with the SSO identifier URI, consent redirect, and token-store client preauthorization."  
> Caption: "Saving the token-store registration alone doesn't finish SSO."

The generic OAuth callback ending in `/oAuthRedirect` is **not** the SSO callback ending in `/oAuthConsentRedirect`.

## 5. Align audiences and authorization

Microsoft's SSO instructions require the new identifier URI to be recognized by your resource. Add it to the resource app and configure it as an accepted audience alias for that same API. Also accept the same app's client ID where the token version requires it.

There is an important version detail: [Entra's access-token reference](https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference) specifies that **v2 access tokens always use the API's client ID as `aud`**. The SSO Application ID URI isn't guaranteed to appear literally in `aud`.

The [gateway policy example](examples/apim-policy.xml) therefore configures both the exact SSO URI and its resource client ID, while retaining a v2-only claim requirement. The backend must use the same intended-resource set and the tenant-specific v2 issuer. For the configured v2 flow, expect the GUID audience in actual validated tokens. Don't switch to a different API audience or disable audience checks to resolve a mismatch.

| Check | Required value |
| --- | --- |
| Signature and lifetime | Verify using trusted Entra signing keys; require a valid expiration and not-before time. |
| `iss` | `https://login.microsoftonline.com/<TENANT_ID>/v2.0` |
| `tid` | `TENANT_ID` |
| `ver` | `2.0` |
| Intended audience | `API_CLIENT_ID`, with the exact same-resource SSO URI configured as an alias. |
| `azp` / client application | Microsoft Enterprise token-store client ID above. |
| `scp` | Contains the space-delimited permission `catalog.read`. |

Require **all** of these checks. Requiring `scp` rejects app-only tokens, which carry no delegated scope. If you later need user identity for rate limiting or auditing, use `tid` plus `oid`, not email or display name.

The API access token isn't a Microsoft Graph token. This design doesn't perform an on-behalf-of exchange and doesn't forward the user token to an API-key backend. A downstream API requiring its own delegated token needs a separate, explicitly designed OBO implementation.

## 6. Bind the Cowork manifest

The examples use **Microsoft 365 app manifest v1.28**. The connector's authorization object is the same in v1.29:

```json
{
  "authorization": {
    "type": "OAuthPluginVault",
    "referenceId": "REPLACE_WITH_SSO_REGISTRATION_ID"
  }
}
```

This object belongs under `agentConnectors[].toolSource.remoteMcpServer`. The `referenceId` value is the **Microsoft Entra SSO registration ID** returned in section 3. Don't paste the API plugin manifest's `auth.reference_id` structure into a Cowork app manifest.

Continue with [Build and deploy](build-and-deploy.md), then [Package and validate](package-and-validate.md). Treat first sign-in, consent, renewal, and expired tokens as separate acceptance cases.
