---
export: Opus4_7
model: claude-opus-4-7
effort: high
run: effort-high_run1
prompt: "L2_8 EDTA competitive binding between copper and zinc"
conversation: https://claude.ai/chat/fdf123bd-8d36-4e6e-b286-633923d129f4
started: 2026-09-17T01:58:49.599935+00:00
finished: 2026-09-17T02:01:30.569055+00:00
stop_reason: end_turn
---
## Setup

With EDTA sub-stoichiometric (1 mM ligand for 2 mM of metal), Cu and Zn compete for a single equivalent of Y. At pH 6, protonation of EDTA lowers the effective [Y⁴⁻], so the appropriate quantities are the **conditional stability constants** K′ = K/α_Y(H).

**α_Y(H) at pH 6** (using pKa's 2.0, 2.67, 6.16, 10.26 at I = 0.1 M):

$$\alpha_{Y(H)} = 1 + \tfrac{[H^+]}{K_{a4}} + \tfrac{[H^+]^2}{K_{a4}K_{a3}} + \tfrac{[H^+]^3}{K_{a4}K_{a3}K_{a2}} + \tfrac{[H^+]^4}{K_{a4}K_{a3}K_{a2}K_{a1}} \approx 4.45\times10^{4}$$

so log α_Y(H) = 4.65.

**Conditional constants** (log K from Martell–Smith at I = 0.1 M):

| Complex | log K | log K′ (= log K − 4.65) |
|---|---|---|
| CuY²⁻ | 18.78 | **14.13** |
| ZnY²⁻ | 16.44 | **11.79** |

Metal hydrolysis at pH 6 is negligible for both (α_M(OH) ≈ 1.01 for Cu, ~1.00 for Zn).

## The competition reduces to a ligand-exchange equilibrium

$$\mathrm{Cu^{2+} + ZnY^{2-} \rightleftharpoons CuY^{2-} + Zn^{2+}} \qquad K_{ex}=\frac{K'_{CuY}}{K'_{ZnY}} = \frac{K_{CuY}}{K_{ZnY}}=10^{2.34}=219$$

(α_Y(H) cancels, so K_ex is pH-independent.)

Because K′_Cu·C_Cu ≈ 10¹¹ ≫ 1 and K′_Zn·C_Zn ≈ 10⁹ ≫ 1, essentially all the EDTA is complexed ([Y′] ≪ 10⁻⁶ M), and mass balance forces:

$$[CuY]+[ZnY] \approx 10^{-3}\ \text{M},\quad [Cu^{2+}]=10^{-3}-[CuY],\quad [Zn^{2+}]=10^{-3}-[ZnY]$$

With **equal metal totals**, symmetry gives [CuY] = [Zn²⁺] and [ZnY] = [Cu²⁺], so K_ex reduces to:

$$\frac{[CuY]^2}{[ZnY]^2}=K_{ex}\quad\Rightarrow\quad\frac{[CuY]}{[ZnY]}=\sqrt{219}=14.8$$

Combining with the mass balance:

$$[CuY]=\frac{\sqrt{K_{ex}}}{1+\sqrt{K_{ex}}}\times 10^{-3}=0.937\ \text{mM},\quad [ZnY]=0.063\ \text{mM}$$

## Speciation of the shared pot

| Species | Concentration (M) | % of its metal |
|---|---|---|
| CuY²⁻ | 9.37 × 10⁻⁴ | 93.7 % of Cu_T |
| Cu²⁺ (free) | 6.33 × 10⁻⁵ | 6.3 % of Cu_T |
| ZnY²⁻ | 6.33 × 10⁻⁵ | 6.3 % of Zn_T |
| Zn²⁺ (free) | 9.37 × 10⁻⁴ | 93.7 % of Zn_T |
| Y′ (all free EDTA forms) | ≈ 1 × 10⁻¹³ | — |

**Bound : free ratios**

- Cu: [CuY]/[Cu²⁺] = 0.937 / 0.0633 = **14.8**
- Zn: [ZnY]/[Zn²⁺] = 0.0633 / 0.937 = **0.068** (i.e., 1 : 14.8)

Self-consistency check on Zn: K′_Zn·[Zn²⁺]·[Y′] = (6.17 × 10¹¹)(9.37 × 10⁻⁴)(1.1 × 10⁻¹³) ≈ 6.4 × 10⁻⁵ M = [ZnY] ✓

## Ligand partition and the winner

Of the 1 mM EDTA dose: **93.7 % is sequestered by Cu(II), 6.3 % by Zn(II), and essentially none is free**.

**Cu(II) wins** — quantitatively by the factor √(K_CuY/K_ZnY) = √219 ≈ 14.8. That the winning margin is the *square root* of the K-ratio (not the ratio itself) is the signature of an equal-total, ligand-limited competition: each metal both provides the substrate and steals from the other's complex, and the exchange equilibrium partitions the ligand accordingly. Note the pH cancels out of K_ex, so this partition — 15:1 in Cu's favor — holds across a wide pH window as long as both K′'s remain large enough for the ligand to be fully bound (roughly pH ≳ 4).
