---
title: Package and validate a Cowork MCP plugin
description: Create a v1.28 Microsoft 365 app package with real MCP tool definitions and verify authorization and end-to-end behavior.
ms.date: 10/06/2026
ms.topic: how-to
---

# Package and validate a Cowork MCP plugin

Package the connector only after its real endpoint and SSO registration are known. A syntactically valid package doesn't prove that sign-in, permission enforcement, or a tool invocation works.

> [!NOTE]
> [Learn now recommends the `wiqd` CLI](https://learn.microsoft.com/en-us/microsoft-365/copilot/cowork/cowork-plugin-development) to scaffold and share Cowork plugins. It targets manifest v1.29, where `mcpToolDescription` is optional. It doesn't yet scaffold connector authentication, so you still add the `authorization` object from [the SSO article](configure-secretless-sso.md#6-bind-the-cowork-manifest). The examples here use v1.28 with Microsoft 365 Agents Toolkit, which remains supported.

## 1. Generate tool definitions from the implementation

The source implementation asks its actual MCP SDK server for tool definitions during packaging. The related toolkit likewise rejects empty tool arrays. Reuse that approach instead of hand-writing plausible tool schemas.

The sample's local check command generates the real one-tool definition into `examples\catalog-tools.generated.json`:

```powershell
Set-Location 'C:\D\Cowork\Cowork-MCP-Plugin-Pattern'
python .\validate_examples.py
```

This command makes no network calls and uses fixtures rather than a real backend. It needs the MCP SDK, Pydantic, jsonschema, PyYAML, and Pillow already installed in the selected Python environment; see [example dependencies](examples/requirements.txt) if needed.

If the selected environment doesn't meet the declared dependencies, create a project-local virtual environment and install them there:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\examples\requirements.txt
.\.venv\Scripts\python.exe .\validate_examples.py
```

Dependency installation downloads public packages; the validation command itself is offline. Use the declared MCP 1.26 release line rather than accepting a result from an older globally installed SDK.

Use definitions generated from **your final adapter build**, not the sample's schema, for a different tool implementation. For a remote existing MCP server, use an authorized discovery client and its actual `tools/list` result. Never temporarily remove production authentication merely to obtain descriptions. An ordinary Azure CLI token isn't the Microsoft token-store client and should fail this pattern's client restriction.

Check that the file contains an object with a nonempty `tools` array. Each tool needs a unique name and valid object `inputSchema`. Preserve the SDK's parameter nesting: this sample takes `{"params":{"record_id":"ITEM-42"}}`, not a top-level `record_id`. Keep each tool's `annotations`, including `title` and `readOnlyHint`, so the package matches what the live server reports.

### Why package a tool-description file?

At run time, Cowork discovers tools by calling `tools/list` on the live server with the user's token. The packaged file isn't used for that discovery. It's still worth including:

- Manifest v1.28 requires `mcpToolDescription`; v1.29 makes it optional.
- It records the reviewed tool surface for app review and administrators before anyone signs in.
- Generating it from the build catches schema drift between the package and the deployed adapter.

Regenerate it whenever tools change, and still test authenticated `tools/list` against the deployed endpoint.

## 2. Assemble the package directory

Use this layout in your own build directory:

```text
appPackage\
  manifest.json
  color.png
  outline.png
  tools\
    catalog-tools.json
  skills\
    catalog-lookup\
      SKILL.md
```

Start from [manifest.example.json](examples/manifest.example.json). Replace the illustrative package GUID with a stable GUID you own, all publisher/legal URLs with working URLs, the gateway host with your public endpoint, and `REPLACE_WITH_SSO_REGISTRATION_ID` with the returned SSO auth config ID.

The important connector fields are:

```json
{
  "id": "catalog-mcp",
  "displayName": "Contoso Catalog",
  "description": "Read approved catalog records.",
  "toolSource": {
    "remoteMcpServer": {
      "mcpServerUrl": "https://gateway.example.com/mcp",
      "mcpToolDescription": {
        "file": "tools/catalog-tools.json"
      },
      "authorization": {
        "type": "OAuthPluginVault",
        "referenceId": "REPLACE_WITH_SSO_REGISTRATION_ID"
      }
    }
  }
}
```

Use `authorization.referenceId`, not `reference_id`. Use `mcpToolDescription.file` directly, not a nested `description.file`. Pin `manifestVersion` and `$schema` to the same version (v1.28 in this example). Don't add unsupported root fields such as `packageName`.

Supply `color.png` at **192 x 192** and `outline.png` at **32 x 32**, with approved branding. The article set intentionally doesn't fabricate publisher icons or an uploadable package.

The example manifest also declares an optional skill with `"agentSkills": [{ "folder": "skills/catalog-lookup" }]`. Add `skills\catalog-lookup\SKILL.md` with a frontmatter `name` of `catalog-lookup`. Have the skill instruct Cowork to treat tool output as untrusted data, report errors explicitly, respect bounded results, and stop on access failures. A skill isn't a security boundary. Remove the `agentSkills` entry if you don't ship a skill.

## 3. Validate and package

Validate the completed manifest against the [official v1.28 JSON schema](https://developer.microsoft.com/json-schemas/teams/v1.28/MicrosoftTeams.schema.json). Resolve all referenced files; verify icon dimensions; compare generated tool schemas with the deployed build.

Then run these commands from **your completed plugin project**, not the article directory:

```powershell
atk --version
atk package --manifest-file .\appPackage\manifest.json `
    --output-package-file .\build\catalog-plugin.zip `
    --output-folder .\build
```

Inspect the ZIP: `manifest.json` must be at the root, not under `appPackage`. Include only explicitly approved package files. Exclude `.env`, deployment configuration, credentials, captures, source code, infrastructure templates, and operator receipts.

The local example validator checks schema and SDK contracts; it doesn't certify that placeholder URLs, branding, or token-store records are ready to publish.

## 4. Verify the public boundary without a token

After activating the gateway, perform a bounded anonymous check against **your** endpoint:

```powershell
curl.exe --silent --show-error --max-time 20 --include `
    'https://<gateway-host>/.well-known/oauth-protected-resource/mcp'
curl.exe --silent --show-error --max-time 20 --include `
    --request POST --header 'Content-Type: application/json' `
    --data '{}' 'https://<gateway-host>/mcp'
```

Expected: metadata returns HTTP 200 with the configured resource, issuer, and scopes. The unauthenticated MCP request returns HTTP 401 and a `WWW-Authenticate` challenge referring to that metadata. Neither request proves authenticated acceptance.

Also check that a public direct call to the Container App cannot invoke a tool. Verify the effective network boundary, not just an environment flag or deployment success state.

## 5. Install for a test user

After organizational approval, authenticate and install the package for your own test account:

```powershell
atk auth login
atk auth list
atk install --file-path .\build\catalog-plugin.zip --scope Personal
```

Check the signed-in account before installation. Record returned app identifiers in your private deployment record. In Cowork, open **Sources & Skills > Plugins**, locate the plugin, and enable/connect it as appropriate.

> **Image placeholder - Connect and exercise the plugin**  
> Intended screenshot: Cowork showing the approved catalog plugin and a successful single-record result after sign-in. Capture only after actual acceptance with nonconfidential test data.  
> Alt text: "Catalog plugin connected in Cowork and one authorized record lookup completed."  
> Caption: "A successful lookup verifies more than package installation or a healthy deployment."

Use a known, nonconfidential test record:

> Use only Contoso Catalog. Look up record ITEM-42 with one catalog_get_record call. Do not retry or use another source. If the call fails, report the error rather than saying the record doesn't exist.

Replace `ITEM-42` with a record that exists in your test system; it isn't evidence of a real catalog record.

## 6. Complete the acceptance matrix

| Case | Required observation |
| --- | --- |
| Signed-in user, correct client/scope/resource | Sign-in completes; `initialize`, initialization notification, `tools/list`, and one `tools/call` work through Cowork. |
| Missing/expired/invalid-signature token | HTTP 401 before backend access. |
| Wrong tenant, audience, client, or token version | Rejected, even if some other claims look correct. |
| Missing delegated scope (including app-only tokens) | Rejected; an app-only token is not accepted as a user token. |
| Unassigned user, only if you enabled **Assignment required** | Entra doesn't issue a token; no tool access. |
| Correct authentication, no tool permission | Tool denied without calling the LOB API. |
| Bad input, unexpected response, oversize output | Explicit error; no partial-success or empty-result substitute. |
| Backend unavailable, timeout, or throttling | Sanitized failure; no automatic retry loop. |
| Access-token renewal | A later call succeeds through the supported refresh path, or requests reauthentication as required by policy. A first call doesn't prove renewal. |
| Read-only tool call | Runs without a confirmation prompt where annotation-driven confirmation is available (it's rolling out progressively for non-Microsoft MCP servers). A prompt means `readOnlyHint` or `destructiveHint` is wrong or missing. |
| Multiple permitted calls | Bounds and LOB API concurrency policy hold under the chosen scale. |
| Logging and package review | No credentials, raw tokens, or sensitive payloads captured or distributed. |

Use local signed-token fixtures for exhaustive verifier unit tests. Use actual authorized test identities for end-to-end acceptance; do not broaden client restrictions to make a generic inspector pass. Record timestamp, image digest, package version/hash, result category, and correlation ID, not tokens or payloads.

## 7. Distribute to your organization

When personal acceptance passes, choose how others get the plugin:

| Route | Where users find it | How |
| --- | --- | --- |
| Personal or shared | **Shared with me** in Cowork | Install for yourself with `atk install --scope Personal`, or use `wiqd plugin share` with `--scope users` (named people) or `--scope tenant`. |
| Organization-wide | **Discover** in Cowork | An administrator opens **Microsoft 365 admin center > Manage apps > Upload custom app**, selects **... > Add agent**, and uploads the ZIP, following your app review process. |

Sharing and admin upload control who sees the plugin. Token issuance is controlled separately by Entra (see [Limit who can use the connector](configure-secretless-sso.md#optional-limit-who-can-use-the-connector)).

Public multitenant distribution needs a separate design for consent, authorization, registration restrictions, and publisher requirements. Don't simply change organization access to "Any" for this single-tenant example.

See [operations and troubleshooting](operate-and-troubleshoot.md).
