"""Generate editable Excalidraw, SVG, and PNG from one shared diagram model."""

import html
import json
import math
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
BLUE, GREEN, PURPLE, GRAY = "#0078D4", "#107C10", "#5C2D91", "#495057"
FONT = Path(r"C:\Windows\Fonts\arial.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\arialbd.ttf")


class Diagram:
    def __init__(self, name, width, height, title, description):
        self.name, self.width, self.height = name, width, height
        self.title, self.description = title, description
        self.items = []

    def text(self, x, y, text, size=24, bold=False, max_width=None):
        font = ImageFont.truetype(str(FONT_BOLD if bold else FONT), size)
        width = math.ceil(font.getlength(text)) + 4
        if max_width is not None and width > max_width:
            raise ValueError(f"Text exceeds available width: {text}")
        self.items.append(dict(kind="text", x=x, y=y, width=width, height=size * 2.5,
                               text=text, size=size, bold=bold))

    def box(self, x, y, width, height, lines, color=BLUE, fill="#CFE4FA", size=24):
        self.items.append(dict(kind="rect", x=x, y=y, width=width, height=height,
                               color=color, fill=fill))
        line_height = size * 1.55
        start = y + max(24, (height - len(lines) * line_height) / 2)
        for index, line in enumerate(lines):
            self.text(x + 24, start + index * line_height, line, size,
                      bold=index == 0, max_width=width - 48)

    def container(self, x, y, width, height, title, color=BLUE, size=28):
        self.items.append(dict(kind="rect", x=x, y=y, width=width, height=height,
                               color=color, fill="transparent"))
        self.text(x + 25, y + 23, title, size, True, width - 50)

    def arrow(self, points, color=BLUE, dashed=False):
        self.items.append(dict(kind="arrow", points=points, color=color, dashed=dashed))

    def legend(self, y):
        for x, color, label, dashed in (
            (65, BLUE, "Request", False),
            (370, GREEN, "Result / response", False),
            (820, PURPLE, "Identity / dependency", True),
            (1370, GRAY, "Sanitized telemetry", True),
        ):
            self.arrow([(x, y + 15), (x + 75, y + 15)], color, dashed)
            self.text(x + 95, y, label, 24)

    def export(self):
        image = Image.new("RGB", (self.width, self.height), "white")
        draw = ImageDraw.Draw(image)
        svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
               f'viewBox="0 0 {self.width} {self.height}" role="img" aria-labelledby="title desc">',
               f'<title id="title">{html.escape(self.title)}</title>',
               f'<desc id="desc">{html.escape(self.description)}</desc>',
               '<rect width="100%" height="100%" fill="white"/>']
        elements = []
        for index, item in enumerate(self.items):
            element = dict(id=f"{self.name}-{index}", angle=0, strokeColor=item.get("color", "#000000"),
                           backgroundColor="transparent", fillStyle="solid", strokeWidth=2,
                           strokeStyle="solid", roughness=0, opacity=100, groupIds=[], frameId=None,
                           seed=index + 100, version=1, versionNonce=index + 300, isDeleted=False,
                           boundElements=None, updated=1, link=None, locked=False)
            kind = item["kind"]
            if kind in ("rect", "text"):
                x, y, w, h = (item[k] for k in ("x", "y", "width", "height"))
                if min(x, y) < 0 or x + w > self.width or y + h > self.height:
                    raise ValueError(f"Element outside canvas: {item}")
                element.update(x=x, y=y, width=w, height=h)
            if kind == "rect":
                fill = item["fill"]
                color = item["color"]
                draw.rounded_rectangle((x, y, x + w, y + h), radius=16,
                                       fill=None if fill == "transparent" else fill,
                                       outline=color, width=3)
                svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" '
                           f'fill="{"none" if fill == "transparent" else fill}" stroke="{color}" stroke-width="3"/>')
                element.update(type="rectangle", backgroundColor=fill, roundness={"type": 3})
            elif kind == "text":
                size, text = item["size"], item["text"]
                font = ImageFont.truetype(str(FONT_BOLD if item["bold"] else FONT), size)
                draw.text((x, y), text, font=font, fill="#000000", anchor="lt")
                svg.append(f'<text x="{x}" y="{y + size * 0.92}" font-family="Arial, Helvetica, sans-serif" '
                           f'font-size="{size}" font-weight="{700 if item["bold"] else 400}" '
                           f'fill="#000000">{html.escape(text)}</text>')
                element.update(type="text", text=text, originalText=text, fontSize=size, fontFamily=2,
                               textAlign="left", verticalAlign="top", baseline=size, containerId=None,
                               autoResize=True, lineHeight=1.25, strokeColor="#000000")
            else:
                points, color = item["points"], item["color"]
                for a, b in zip(points, points[1:]):
                    if item["dashed"]:
                        dx, dy = b[0] - a[0], b[1] - a[1]
                        length = math.hypot(dx, dy)
                        for offset in range(0, math.ceil(length), 20):
                            stop = min(offset + 12, length)
                            draw.line((a[0] + dx * offset / length, a[1] + dy * offset / length,
                                       a[0] + dx * stop / length, a[1] + dy * stop / length), fill=color, width=4)
                    else:
                        draw.line((a, b), fill=color, width=4)
                a, b = points[-2:]
                angle = math.atan2(b[1] - a[1], b[0] - a[0])
                head = [b, (b[0] - 19 * math.cos(angle - 0.43), b[1] - 19 * math.sin(angle - 0.43)),
                        (b[0] - 19 * math.cos(angle + 0.43), b[1] - 19 * math.sin(angle + 0.43))]
                draw.polygon(head, fill=color)
                coords = " ".join(f"{px},{py}" for px, py in points)
                dash = ' stroke-dasharray="12 8"' if item["dashed"] else ""
                svg.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="4"{dash}/>')
                svg.append(f'<polygon points="{" ".join(f"{px},{py}" for px, py in head)}" fill="{color}"/>')
                ox, oy = points[0]
                relative = [[px - ox, py - oy] for px, py in points]
                element.update(type="arrow", x=ox, y=oy,
                               width=max(p[0] for p in relative) - min(p[0] for p in relative),
                               height=max(p[1] for p in relative) - min(p[1] for p in relative),
                               points=relative, startBinding=None, endBinding=None,
                               startArrowhead=None, endArrowhead="arrow", lastCommittedPoint=None,
                               elbowed=False, strokeWidth=3,
                               strokeStyle="dashed" if item["dashed"] else "solid")
            elements.append(element)
        svg.append("</svg>")
        output = "\n".join(svg) + "\n"
        ET.fromstring(output)
        (ROOT / f"{self.name}.svg").write_text(output, encoding="utf-8")
        image.save(ROOT / f"{self.name}.png")
        document = dict(type="excalidraw", version=2, source="GitHub Copilot",
                        elements=elements, appState={"viewBackgroundColor": "#ffffff", "gridSize": None},
                        files={})
        (ROOT / f"{self.name}.excalidraw").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        return {"name": self.name, "dimensions": [self.width, self.height],
                "elements": len(elements), "textBoundsChecked": True, "svgParsed": True,
                "rendering": "SVG and Pillow PNG from identical geometry; editable Excalidraw source",
                "excalidrawEditorRoundTripTested": False}


def data_flow():
    d = Diagram("cowork-mcp-data-flow", 2460, 1470, "From a user question to a bounded LOB API result",
                "Generic Cowork MCP flow with secretless Entra SSO, an Entra-protected APIM MCP endpoint, a private adapter, "
                "and optional API-key LOB API access using managed identity and Key Vault.")
    d.text(60, 45, d.title, 42, True)
    d.text(60, 112, "Reusable target pattern | Single tenant | Read-only tools | APIM and adapter host are replaceable", 26)
    d.box(360, 205, 740, 180, ["Microsoft Entra SSO + token store", "Delegated access for the signed-in user",
                            "SSO client ID registration; no client secret"], PURPLE, "#E8DAEF", 26)
    d.box(1210, 205, 760, 180, ["Resource application binding", "SSO URI + Web consent callback",
                             "Preauthorize the Microsoft token-store client"], PURPLE, "#E8DAEF", 26)
    d.arrow([(1100, 290), (1210, 290)], PURPLE, True)
    d.container(1010, 470, 880, 855, "Customer Azure | public gateway + private adapter", size=27)
    d.box(60, 595, 245, 270, ["1. User", "Ask a business", "question"], size=28)
    d.box(395, 555, 465, 365, ["2. Cowork + plugin", "Select an approved tool", "Send structured arguments",
                            "No conversation field", "in the sample tool schema"], size=27)
    d.box(1060, 570, 325, 335, ["3. Public APIM", "Entra-protected /mcp", "Check tenant + scope", "Apply rate limit",
                             "Forward /mcp"], size=25)
    d.box(1480, 570, 355, 335, ["4. Private MCP", "Revalidate user token", "Check tool permission",
                             "Bound input / output", "One read operation"], GREEN, "#DFF6DD", 25)
    d.box(2040, 570, 355, 335, ["5. LOB API", "Fixed HTTPS origin", "API key if required",
                             "No user token", "Validate the response"], GREEN, "#DFF6DD", 25)
    for left, right in ((305, 395), (860, 1060), (1385, 1480), (1835, 2040)):
        d.arrow([(left, 685), (right - 8, 685)], BLUE)
        d.arrow([(right, 845), (left + 8, 845)], GREEN)
    d.text(875, 594, "HTTPS + JWT", 19)
    d.text(875, 630, "MCP request", 19)
    d.text(1910, 570, "HTTPS", 22)
    d.text(1910, 607, "Backend key", 22)
    d.text(1910, 644, "if required", 22)
    d.arrow([(625, 385), (625, 545)], PURPLE, True)
    d.text(650, 425, "Delegated user token", 24)
    d.box(1380, 1120, 455, 160, ["Key Vault (API-key variant)", "Managed identity reads the key",
                              "Private endpoint + secret RBAC"], PURPLE, "#E8DAEF", 24)
    d.arrow([(1790, 905), (1790, 1110)], PURPLE, True)
    d.text(1480, 975, "Separate backend credential", 24)
    d.text(1480, 1015, "via managed identity", 24)
    d.box(60, 1110, 900, 185, ["Azure Monitor | sanitized operational evidence",
                             "Correlation IDs, time, latency, status, error category",
                             "No prompt, token, key, or response-body capture"], GRAY, "#F3F2F1", 24)
    d.arrow([(1185, 905), (1185, 1050), (590, 1050), (590, 1100)], GRAY, True)
    d.text(395, 956, "6. Results return through APIM.", 27)
    d.text(395, 1000, "Cowork summarizes for the user.", 27)
    d.text(60, 1350, "HTTP 200 is not proof of tool success. Check MCP isError and the LOB API result.", 26)
    d.legend(1405)
    return d


def network():
    d = Diagram("cowork-mcp-network", 2600, 2020, "Cowork MCP | Network and identity architecture",
                "Public APIM reaches a private Container Apps environment. The adapter calls an "
                "LOB API, optionally retrieves its key through a private Key Vault endpoint, "
                "and uses managed identity to pull its image. APIM and the adapter need outbound access to Entra signing keys.")
    d.text(65, 45, d.title, 43, True)
    d.text(65, 118, "Example deployment | Azure public cloud | Other adapter hosts work | Illustrative subnets", 27)
    d.box(65, 195, 2470, 95, ["Secretless SSO authenticates the user; managed identity authenticates the Azure workload."],
          PURPLE, "#E8DAEF", 29)
    d.box(100, 345, 495, 190, ["Microsoft 365 Copilot Cowork", "v1.28 plugin + OAuthPluginVault",
                             "Public gateway: HTTPS /mcp"], size=26)
    d.box(780, 335, 835, 205, ["Microsoft Entra ID + Enterprise token store",
                             "Resource app + SSO auth config; no client secret",
                             "Delegated scope; token-store client preauthorized"], PURPLE, "#E8DAEF", 25)
    d.arrow([(780, 432), (605, 432)], PURPLE, True)
    d.box(2050, 345, 480, 190, ["LOB API", "HTTPS endpoint", "Backend key if required; no user JWT"], size=24)
    d.container(65, 630, 2470, 1190, "Customer Azure subscription | solution-owned resources", GRAY, 28)
    d.container(100, 735, 1785, 665, "Virtual network | example 10.0.0.0/16", BLUE, 29)
    d.container(135, 835, 455, 510, "APIM subnet | 10.0.1.0/24", BLUE, 25)
    d.container(695, 835, 735, 510, "Container Apps subnet | 10.0.2.0/24", BLUE, 25)
    d.text(720, 893, "Dedicated subnet delegated to Microsoft.App/environments", 22)
    d.container(1515, 835, 330, 510, "Private endpoints", PURPLE, 25)
    d.text(1540, 894, "Example 10.0.3.0/24", 23)
    d.box(165, 965, 395, 270, ["Public APIM gateway", "External VNet topology", "Entra token validation",
                             "Private backend route", "No body buffering"], size=25)
    d.container(720, 945, 685, 375, "INTERNAL Container Apps environment", BLUE, 26)
    d.box(760, 1020, 605, 95, ["Internal ingress | private VIP | HTTPS 443"], size=24)
    d.box(760, 1170, 605, 115, ["Private Python MCP adapter | HTTP 8000",
                             "Independent JWT and tool-permission checks"], GREEN, "#DFF6DD", 24)
    d.box(1540, 1135, 280, 140, ["Key Vault PE", "Private IP", "API-key variant"], PURPLE, "#E8DAEF", 23)
    d.box(2050, 1115, 455, 180, ["Key Vault (conditional)", "Backend API key only",
                              "Private access + secret-scoped RBAC"], PURPLE, "#E8DAEF", 23)
    d.arrow([(200, 535), (200, 605), (40, 605), (40, 1060), (155, 1060)], BLUE)
    d.text(250, 563, "1 | Public HTTPS 443", 24)
    d.arrow([(560, 1060), (750, 1060)], BLUE)
    d.arrow([(750, 1093), (570, 1093)], GREEN)
    d.text(600, 953, "2 | Same", 21)
    d.text(600, 985, "user JWT", 21)
    d.arrow([(1050, 1115), (1050, 1160)], BLUE)
    d.arrow([(1120, 1170), (1120, 1125)], GREEN)
    d.arrow([(1365, 1265), (1530, 1265)], PURPLE, True)
    d.arrow([(1820, 1210), (2040, 1210)], PURPLE, True)
    d.text(1880, 1150, "Private Link", 23)
    d.text(1538, 1290, "3 | Identity-based read", 20)
    d.arrow([(1365, 1200), (1470, 1200), (1470, 580), (2290, 580), (2290, 545)], BLUE)
    d.arrow([(2350, 545), (2350, 610), (1505, 610), (1505, 1240), (1375, 1240)], GREEN)
    d.text(1660, 548, "4 | Direct HTTPS to LOB API", 24)
    d.box(135, 1455, 865, 150, ["Private DNS | zones linked to the VNet",
                              "Environment default domain: * and @ to private VIP",
                              "privatelink.vaultcore.azure.net for the API-key variant"], size=24)
    d.box(1090, 1455, 690, 150, ["User-assigned managed identity",
                               "Attached to adapter; not an extra network hop",
                               "Registry pull + Key Vault read (when needed)"], PURPLE, "#E8DAEF", 24)
    d.arrow([(1310, 1455), (1310, 1408), (1260, 1408), (1260, 1295)], PURPLE, True)
    d.box(2050, 1455, 455, 150, ["Container Registry", "Identity-based image pull",
                              "Authenticated HTTPS endpoint"], GRAY, "#F3F2F1", 24)
    d.arrow([(1780, 1490), (2010, 1490), (2010, 1505), (2040, 1505)], PURPLE, True)
    d.box(135, 1660, 1645, 115, ["Application Insights + Log Analytics",
                               "Sanitized status, correlation and latency; no prompt, token, key, or response-body capture"],
          GRAY, "#F3F2F1", 25)
    d.arrow([(560, 1210), (630, 1210), (630, 1410), (1020, 1410),
             (1020, 1630), (460, 1630), (460, 1650)], GRAY, True)
    d.arrow([(850, 1285), (850, 1425), (1040, 1425), (1040, 1650)], GRAY, True)
    d.text(1900, 1680, "Preserve platform-managed resources.", 24)
    d.text(1900, 1720, "Egress via NAT gateway or firewall.", 24)
    d.text(100, 1850, "App ingress is VNet-visible within an internal environment; allow only the APIM subnet. Platform probes remain permitted.", 25)
    d.text(100, 1890, "Allow outbound HTTPS from APIM and the adapter to Entra (signing keys), plus the LOB API, registry, and platform dependencies.", 25)
    d.legend(1940)
    return d


if __name__ == "__main__":
    results = [data_flow().export(), network().export()]
    (ROOT / "diagram-validation.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print("Generated two editable diagrams and matching SVG/PNG renders.")
