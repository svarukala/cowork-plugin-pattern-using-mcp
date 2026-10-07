---
title: Reusable Cowork MCP architecture diagrams
description: Editable and article-ready versions of the conceptual flow and network architecture.
ms.date: 09/24/2026
ms.topic: reference
---

# Reusable Cowork MCP architecture diagrams

These diagrams are original generic adaptations of the supplied conceptual-flow and network references. They describe the recommended target design, not the live status of a deployment.

| Diagram | Article-ready vector | Raster image | Editable source |
| --- | --- | --- | --- |
| Question to bounded result | [SVG](cowork-mcp-data-flow.svg) | [PNG](cowork-mcp-data-flow.png) | [Excalidraw](cowork-mcp-data-flow.excalidraw) |
| Network and identity architecture | [SVG](cowork-mcp-network.svg) | [PNG](cowork-mcp-network.png) | [Excalidraw](cowork-mcp-network.excalidraw) |

Blue arrows denote requests, green arrows denote result/response flow, purple dashed arrows denote identity/dependency access, and gray dashed arrows denote sanitized telemetry. Text is black; enclosing trust-boundary boxes are transparent.

SSO registration is separate from managed identity. Key Vault/backend-key paths are conditional on backend authentication. Neither diagram contains an application Blob coordination component. The network diagram retains registry, private DNS, platform ingress, and monitoring rather than removing unrelated platform requirements.

Open the `.excalidraw` files in [Microsoft's Excalidraw instance](https://aka.ms/excalidraw) to edit. The SVG/PNG exports and editable sources share the same programmatically authored geometry; they aren't screenshots from an Excalidraw editor. Editor import/export round-trip acceptance wasn't performed.

The final PNGs were visually reviewed at full image scale on September 24, 2026. Labels, arrows, trust boundaries, and legends were checked; crossed labels and a telemetry path through a supporting-service panel were corrected before the final render. The SVGs were XML-parsed and generated from the same geometry. Text dimensions, black text, transparent enclosing boxes, unique IDs, and matching raster/vector canvas dimensions are also checked by the offline validator.

To regenerate all six files on Windows, use Python with Pillow and Windows Arial fonts:

```powershell
python .\diagrams\generate_diagrams.py
```

The generator overwrites its six named outputs and `diagram-validation.json`; preserve manual diagram edits before rerunning it. Portal and Cowork UI screenshot placeholders in the articles remain editorial requests for authentic, redacted screenshots.
