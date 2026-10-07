"""Offline checks for the article set; not deployment or SSO acceptance."""

import asyncio
import importlib.metadata
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

sys.dont_write_bytecode = True
import yaml
from jsonschema import Draft7Validator, Draft202012Validator, FormatChecker
from pydantic import ValidationError
from PIL import Image

from examples import catalog_tools as sample

ROOT = Path(__file__).resolve().parent
CHECKS = []


def check(condition, description):
    if not condition:
        raise AssertionError(description)
    CHECKS.append(description)


def read_json(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


class FixtureBackend:
    def __init__(self, value=None, error=None, delay=0):
        self.value = {"id": "ITEM-42", "title": "Fixture only"} if value is None else value
        self.error = error
        self.delay = delay
        self.calls = 0

    async def lookup(self, record_id):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.value


async def validate_tools():
    principal = sample.CatalogPrincipal("fixture-tenant:fixture-user", frozenset({"lookup"}))
    params = sample.LookupInput(record_id="ITEM-42")
    server = sample.create_mcp(FixtureBackend())
    tools = await server.list_tools()
    check(len(tools) == 1 and tools[0].name == "catalog_get_record", "SDK registers exactly the documented tool")
    check(tools[0].annotations.readOnlyHint is True and tools[0].annotations.destructiveHint is False
          and bool(tools[0].annotations.title), "SDK tool is annotated read-only with a confirmation title")
    schema = tools[0].inputSchema
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    check(validator.is_valid({"params": {"record_id": "ITEM-42"}}), "Tool schema accepts documented params nesting")
    check(not validator.is_valid({"record_id": "ITEM-42"}), "Tool schema rejects flattened arguments")
    for invalid in ({}, {"record_id": 42}, {"record_id": ""}, {"record_id": "../x"},
                    {"record_id": "x" * 65}, {"record_id": "x", "extra": True}):
        try:
            sample.LookupInput(**invalid)
        except ValidationError:
            continue
        raise AssertionError(f"Invalid fixture accepted: {invalid!r}")
    check(True, "Strict input rejects missing, wrong-type, blank, path, oversize, and extra values")
    for denied in (None, sample.CatalogPrincipal("", frozenset({"lookup"})),
                   sample.CatalogPrincipal("fixture-user", frozenset())):
        backend = FixtureBackend()
        result = await sample.execute_lookup(backend, params, denied)
        check(result.isError and backend.calls == 0, "Denied principal cannot invoke backend")
    backend = FixtureBackend()
    result = await sample.execute_lookup(backend, params, principal)
    check(not result.isError and backend.calls == 1, "Authorized lookup invokes backend once")
    check(json.loads(result.content[0].text) == result.structuredContent, "Text and structured MCP result match")
    for value in (["not", "an", "object"], {"value": float("nan")}):
        result = await sample.execute_lookup(FixtureBackend(value), params, principal)
        check(result.isError and result.structuredContent["error"]["code"] == "invalid_response",
              "Unsupported or nonfinite backend result fails explicitly")
    base = {"record": {"value": ""}, "metadata": {"record_count": 1}}
    overhead = len(json.dumps(base, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    for extra, succeeds in ((0, True), (1, False)):
        backend = FixtureBackend({"value": "x" * (sample.RESPONSE_BYTES - overhead + extra)})
        result = await sample.execute_lookup(backend, params, principal)
        check((not result.isError) == succeeds, f"Exact serialized byte limit boundary, extra={extra}")
    result = await sample.execute_lookup(
        FixtureBackend({"value": "\u00e9" * sample.RESPONSE_BYTES}), params, principal
    )
    check(result.isError, "Output cap counts UTF-8 bytes, not characters")
    with patch.object(sample, "DEADLINE_SECONDS", 0.01):
        backend = FixtureBackend(delay=0.1)
        result = await sample.execute_lookup(backend, params, principal)
    check(result.structuredContent["error"]["code"] == "deadline_exceeded" and backend.calls == 1,
          "Deadline failure is explicit and doesn't retry")
    backend = FixtureBackend(error=RuntimeError("private fixture diagnostic"))
    result = await sample.execute_lookup(backend, params, principal)
    check(result.isError and "private fixture diagnostic" not in result.content[0].text,
          "Backend exception details aren't returned")
    try:
        await sample.execute_lookup(FixtureBackend(error=asyncio.CancelledError()), params, principal)
    except asyncio.CancelledError:
        check(True, "Cancellation propagates rather than returning success")
    else:
        raise AssertionError("Cancellation swallowed")
    document = {"tools": [tool.model_dump(mode="json", exclude_none=True) for tool in tools]}
    (ROOT / "examples" / "catalog-tools.generated.json").write_text(
        json.dumps(document, indent=2) + "\n", encoding="utf-8"
    )


def validate_documents():
    for path in (p for p in ROOT.rglob("*.py") if not {".validation-venv", ".venv"}.intersection(p.parts)):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    check(True, "All local Python examples and utilities parse")
    for path in (p for p in ROOT.rglob("*.md") if not {".validation-venv", ".venv", "meeting"}.intersection(p.parts)):
        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        check(len(parts) == 3 and not parts[0].strip(), f"{path.name}: Learn-style frontmatter")
        frontmatter = yaml.safe_load(parts[1])
        check(all(k in frontmatter for k in ("title", "description", "ms.date", "ms.topic")),
              f"{path.name}: required metadata")
        for match in re.finditer(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            link = match.group(1)
            if re.match(r"^[a-zA-Z]+:", link):
                continue
            name, _, anchor = link.partition("#")
            target = path.parent / name if name else path
            if target == ROOT / "validation-report.json":
                continue
            check(target.is_file(), f"{path.name}: local link {link}")
            if anchor and target.suffix == ".md":
                headings = re.findall(r"^#{1,6}\s+(.+)$", target.read_text(encoding="utf-8"), re.M)
                anchors = {re.sub(r"[^a-z0-9 _-]", "", h.lower()).replace(" ", "-") for h in headings}
                check(anchor in anchors, f"{path.name}: heading anchor {anchor}")
        for lang, body in re.findall(r"```(\w*)\n(.*?)\n```", text, re.S):
            if lang == "json":
                json.loads(body)
    check(True, "Fenced JSON examples parse")
    for path in ROOT.glob("*.md"):
        if path.name == "implementation-review.md":
            continue
        found = re.search(r"(?<!of-)Business API|catalog-research|allowedUserObjectIds|Catalog\.Reader|approved[- ]user|"
                          r"\bBlob\b|\blease\b", path.read_text(encoding="utf-8"), re.I)
        check(found is None, f"{path.name}: no removed allowlist, role, Blob, or legacy naming")
    for path in (ROOT / "examples").glob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        check(not re.search(r"BlobLeaseCoordinator|RequestCoordinator|COORDINATION_|azure-storage-blob|acquire_lease|Storage Blob Data Contributor", text, re.I),
              f"{path.name}: no domain or application coordination dependency")
    manifest = read_json("examples/manifest.example.json")
    schema = read_json("references/m365-manifest-v1.28.schema.json")
    Draft7Validator(schema, format_checker=FormatChecker()).validate(manifest)
    check(True, "Example manifest matches downloaded official v1.28 schema")
    remote = manifest["agentConnectors"][0]["toolSource"]["remoteMcpServer"]
    settings = read_json("examples/runtime-settings.example.json")
    metadata = read_json("examples/oauth-resource.example.json")
    check(remote["authorization"]["type"] == "OAuthPluginVault", "Manifest uses OAuthPluginVault")
    check(manifest.get("agentSkills") == [{"folder": "skills/catalog-lookup"}],
          "Manifest declares the catalog-lookup skill folder")
    check(remote["mcpServerUrl"] == settings["publicMcpUrl"] == metadata["resource"],
          "Manifest, runtime, and metadata use the same endpoint")
    check(settings["requiredScope"] == "catalog.read"
          and not {"requiredRole", "allowedUserObjectIds"}.intersection(settings),
          "Runtime authorizes on the delegated scope without a user allowlist or app role")
    check(metadata["scopes_supported"] == [settings["ssoApplicationIdUri"] + "/catalog.read"],
          "Metadata scope uses the configured SSO resource URI")
    policy = ET.parse(ROOT / "examples" / "apim-policy.xml").getroot()
    auth = policy.find("./inbound/validate-azure-ad-token")
    check(auth is not None, "Gateway uses Entra-specific validation policy")
    check(auth.findtext("./client-application-ids/application-id") == settings["allowedClientIds"][0],
          "Gateway and runtime restrict the Microsoft token-store client")
    claims = {c.attrib["name"]: [v.text for v in c.findall("value")] for c in auth.findall("./required-claims/claim")}
    check(claims == {"tid": ["__TENANT_ID__"], "ver": ["2.0"], "scp": ["catalog.read"]},
          "Gateway requires tenant, v2 token, and delegated scope with no user allowlist or app role")
    check(auth.find("./required-claims/claim[@name='scp']").get("separator") == " ",
          "Delegated scopes are space-separated")
    check([a.text for a in auth.findall("./audiences/audience")] ==
          ["__API_CLIENT_ID__", "__SSO_APPLICATION_ID_URI__"], "Gateway audience aliases identify the same configured API")
    check(policy.find("./backend/forward-request").get("buffer-response") == "false",
          "Gateway doesn't buffer MCP responses")
    check(policy.find("./inbound/rewrite-uri").get("template") == "/mcp", "Gateway backend route is /mcp")


def validate_diagrams():
    for stem in ("cowork-mcp-data-flow", "cowork-mcp-network"):
        document = read_json(f"diagrams/{stem}.excalidraw")
        check(document["type"] == "excalidraw" and document["version"] == 2,
              f"{stem}: editable Excalidraw document")
        elements = document["elements"]
        check(len({e["id"] for e in elements}) == len(elements), f"{stem}: unique element IDs")
        text = [e for e in elements if e["type"] == "text"]
        check(all(e["width"] > 0 and e["height"] > 0 and e["strokeColor"] == "#000000" for e in text),
              f"{stem}: visible, dimensioned black text")
        check(not re.search(r"BlobLease|COORDINATION_|lease storage|blob storage",
                            " ".join(e["text"] for e in text), re.I),
              f"{stem}: generic labels without application storage mechanism")
        rectangles = [e for e in elements if e["type"] == "rectangle"]
        for outer in rectangles:
            contains_box = any(
                inner["id"] != outer["id"] and inner["x"] >= outer["x"] and inner["y"] >= outer["y"]
                and inner["x"] + inner["width"] <= outer["x"] + outer["width"]
                and inner["y"] + inner["height"] <= outer["y"] + outer["height"]
                for inner in rectangles
            )
            if contains_box:
                check(outer["backgroundColor"] == "transparent", f"{stem}: transparent trust-boundary container")
        svg = ET.parse(ROOT / "diagrams" / f"{stem}.svg").getroot()
        check(svg.get("role") == "img", f"{stem}: accessible SVG role")
        with Image.open(ROOT / "diagrams" / f"{stem}.png") as image:
            check(image.size == (int(svg.get("width")), int(svg.get("height"))),
                  f"{stem}: SVG and PNG dimensions match")
            image.verify()


def main():
    check(importlib.metadata.version("mcp").startswith("1.26."),
          "Validation uses the declared MCP SDK 1.26 release line")
    report = {
        "checkedAtUtc": datetime.now(timezone.utc).isoformat(),
        "kind": "offline-document-and-integration-example-validation",
        "sdkVersion": importlib.metadata.version("mcp"),
        "networkCalls": 0,
        "deploymentTested": False,
        "ssoAcceptanceTested": False,
        "realBackendTested": False,
    }
    try:
        asyncio.run(validate_tools())
        validate_documents()
        validate_diagrams()
        report.update(status="passed", checks=CHECKS, checkCount=len(CHECKS))
    except Exception as error:
        report.update(status="failed", checks=CHECKS, failure=str(error))
        raise
    finally:
        (ROOT / "validation-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Passed {len(CHECKS)} offline checks; no deployment or sign-in tests performed.")


if __name__ == "__main__":
    main()
