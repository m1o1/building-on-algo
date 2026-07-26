# The constant product curve, plotted rather than sketched. k, the reserves, the
# swap and the tangent are all computed here so the drawing cannot drift away
# from the arithmetic the chapter works in prose.
K = 1_000_000
X0, Y0 = 1000, 1000          # the pool before the swap
DX = 250                     # what the trader sends in
X1 = X0 + DX
Y1 = K / X1                  # 800 -> the trader receives 200
TAN_Y = Y0 - DX              # 750 -> what a fixed price would have paid

# The window is cropped tight around the swap. Plotting from the origin would
# push the whole interesting stretch of the curve into a corner and make the
# slippage gap -- the entire point of the figure -- a few pixels tall.
XLO, XHI = 800, 1600
YLO, YHI = 600, 1200
PX0, PX1 = 110, 630
PYB, PYT = 560, 80
SX = (PX1 - PX0) / (XHI - XLO)
SY = (PYB - PYT) / (YHI - YLO)

def px(x): return PX0 + (x - XLO) * SX
def py(y): return PYB - (y - YLO) * SY

pts, x = [], 850
while x <= 1600.001:
    pts.append((px(x), py(K / x)))
    x += 5
path = "M " + " L ".join(f"{a:.2f} {b:.2f}" for a, b in pts)
tangent = (f"M {px(920):.2f} {py(1080):.2f} L {px(1330):.2f} {py(670):.2f}")

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 780 700" width="780" height="700" font-family="DejaVu Sans, sans-serif">
  <!-- Generated from the arithmetic, not drawn by eye. k = {K:,}; the pool sits at
       ({X0:,}, {Y0:,}); the trader sends {DX} in and takes {int(Y0 - Y1)} out, where a fixed
       price would have paid {DX}. The {DX - int(Y0 - Y1)}-unit gap is the whole lesson, so the
       window is cropped tight enough that the gap is legible. -->
  <style>
    text {{ fill: #111111; }}
    .ax    {{ stroke: #333333; stroke-width: 1.5; fill: none; }}
    .curve {{ stroke: #333333; stroke-width: 2.5; fill: none; }}
    .tan   {{ stroke: #333333; stroke-width: 1.5; fill: none; stroke-dasharray: 6 4; }}
    .gd    {{ stroke: #bbbbbb; stroke-width: 1; stroke-dasharray: 3 3; fill: none; }}
    .move  {{ stroke: #333333; stroke-width: 1.8; fill: none; }}
    .dot   {{ fill: #333333; }}
    .odot  {{ fill: #ffffff; stroke: #333333; stroke-width: 1.8; }}
    .lab   {{ font-size: 12.5px; }}
    .labb  {{ font-size: 13px; font-weight: bold; }}
    .tick  {{ font-size: 11px; fill: #333333; }}
    .axt   {{ font-size: 12.5px; font-style: italic; fill: #333333; }}
    .note  {{ font-size: 12.5px; }}
    .gap   {{ stroke: #333333; stroke-width: 1.5; fill: none; }}
    .panel {{ fill: #fafafa; stroke: #888888; stroke-width: 1; }}
    .k     {{ font-size: 15px; font-weight: bold; }}
  </style>

  <!-- axes -->
  <path class="ax" d="M {PX0} {PYT - 14} L {PX0} {PYB} L {PX1 + 22} {PYB}"/>
  <text class="axt" x="{(PX0 + PX1) / 2:.0f}" y="{PYB + 50}" text-anchor="middle">reserve of asset A held by the pool</text>
  <text class="axt" x="26" y="320" transform="rotate(-90 26 320)" text-anchor="middle">reserve of asset B</text>

  <!-- ticks -->
  <text class="tick" x="{px(1000):.1f}" y="{PYB + 18}" text-anchor="middle">1,000</text>
  <text class="tick" x="{px(1250):.1f}" y="{PYB + 18}" text-anchor="middle">1,250</text>
  <text class="tick" x="{px(1500):.1f}" y="{PYB + 18}" text-anchor="middle">1,500</text>
  <text class="tick" x="{PX0 - 8}" y="{py(1000) + 4:.1f}" text-anchor="end">1,000</text>
  <text class="tick" x="{PX0 - 8}" y="{py(800) + 4:.1f}" text-anchor="end">800</text>
  <text class="tick" x="{PX0 - 8}" y="{py(750) + 4:.1f}" text-anchor="end">750</text>

  <!-- guides -->
  <path class="gd" d="M {PX0} {py(1000):.2f} L {px(1000):.2f} {py(1000):.2f} L {px(1000):.2f} {PYB}"/>
  <path class="gd" d="M {PX0} {py(800):.2f} L {px(1250):.2f} {py(800):.2f} L {px(1250):.2f} {PYB}"/>
  <path class="gd" d="M {PX0} {py(750):.2f} L {px(1250):.2f} {py(750):.2f}"/>

  <!-- the tangent: the price the pool quotes at that instant -->
  <path class="tan" d="{tangent}"/>
  <!-- The label hangs off the tangent's lower end, where the dashed line is
       clearly separate from the curve. Near the tangency point the two are
       within a pixel of each other and a label there points at both. -->
  <path class="gd" d="M {px(1330) + 0.5:.2f} {py(670) + 1:.2f} L {px(1330) + 13.5:.2f} {py(670) + 15:.2f}"/>
  <text class="lab" x="{px(1330) + 17.5:.1f}" y="{py(670) + 20:.1f}">the quoted price</text>

  <!-- the curve -->
  <path class="curve" d="{path}"/>

  <!-- the swap, as a move along the curve -->
  <path class="move" d="M {px(1000):.2f} {py(1000):.2f} L {px(1250):.2f} {py(1000):.2f}"/>
  <path class="move" d="M {px(1250):.2f} {py(1000):.2f} L {px(1250):.2f} {py(800):.2f}"/>
  <circle class="dot"  cx="{px(1000):.2f}" cy="{py(1000):.2f}" r="5"/>
  <circle class="dot"  cx="{px(1250):.2f}" cy="{py(800):.2f}"  r="5"/>
  <circle class="odot" cx="{px(1250):.2f}" cy="{py(750):.2f}"  r="4.5"/>
  <text class="lab" x="{px(1125):.1f}" y="{py(1000) - 10:.1f}" text-anchor="middle">send 250 A</text>
  <text class="lab" x="{px(1250) + 10:.1f}" y="{py(900):.1f}">receive 200 B</text>

  <!-- the slippage bracket -->
  <path class="gap" d="M {px(1250) + 4:.2f} {py(800):.2f} L {px(1250) + 14:.2f} {py(800):.2f} L {px(1250) + 14:.2f} {py(750):.2f} L {px(1250) + 4:.2f} {py(750):.2f}"/>
  <!-- The annotation sits above the bracket rather than beside it: to the right of
       the bracket the curve is still descending through that band and would run
       straight through the third line. -->
  <text class="labb" x="{px(1250) + 26:.1f}" y="{py(800) - 44:.1f}">50 B of slippage</text>
  <text class="lab"  x="{px(1250) + 26:.1f}" y="{py(800) - 26:.1f}">the quoted price would</text>
  <text class="lab"  x="{px(1250) + 26:.1f}" y="{py(800) - 8:.1f}">have paid you 250 B</text>

  <!-- the invariant -->
  <text class="k"   x="530" y="176" text-anchor="middle">x &#215; y = k</text>
  <text class="lab" x="530" y="198" text-anchor="middle">k = 1,000,000</text>

  <!-- the swap, in numbers -->
  <rect class="panel" x="140" y="444" width="270" height="104"/>
  <text class="labb" x="156" y="470">before</text>
  <text class="lab"  x="256" y="470">1,000 A &#215; 1,000 B</text>
  <text class="lab"  x="156" y="492">send</text>
  <text class="lab"  x="256" y="492">250 A</text>
  <text class="lab"  x="156" y="514">receive</text>
  <text class="lab"  x="256" y="514">200 B</text>
  <text class="labb" x="156" y="536">after</text>
  <text class="lab"  x="256" y="536">1,250 A &#215; 800 B</text>

  <!-- footnote -->
  <text class="note" x="20" y="652">The dashed line is the price the pool quotes at that instant. Trade against it and you leave it immediately:</text>
  <text class="note" x="20" y="674">the bigger your order is relative to the reserves, the further down the curve you drag yourself before you are done.</text>
</svg>
'''
# Written beside the other figure sources. Run from anywhere:
#   python3 figures/gen/constant-product-curve.py
import pathlib
OUT = pathlib.Path(__file__).resolve().parent.parent / "src" / "constant-product-curve.svg"
OUT.write_text(svg)
print("wrote", OUT)
print("k:", X1 * Y1, "out:", Y0 - Y1, "fixed-price out:", DX, "slippage:", DX - (Y0 - Y1))
