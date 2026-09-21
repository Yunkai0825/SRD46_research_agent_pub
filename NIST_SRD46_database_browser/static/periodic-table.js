/* ═══════════════════════════════════════════════════════════════════
   periodic-table.js — Interactive periodic table with SRD46 heatmap
   ═══════════════════════════════════════════════════════════════════ */

(function () {
  const ELEMENTS = [
    [1,1,1,"H","Hydrogen"],[1,18,2,"He","Helium"],
    [2,1,3,"Li","Lithium"],[2,2,4,"Be","Beryllium"],[2,13,5,"B","Boron"],[2,14,6,"C","Carbon"],[2,15,7,"N","Nitrogen"],[2,16,8,"O","Oxygen"],[2,17,9,"F","Fluorine"],[2,18,10,"Ne","Neon"],
    [3,1,11,"Na","Sodium"],[3,2,12,"Mg","Magnesium"],[3,13,13,"Al","Aluminium"],[3,14,14,"Si","Silicon"],[3,15,15,"P","Phosphorus"],[3,16,16,"S","Sulfur"],[3,17,17,"Cl","Chlorine"],[3,18,18,"Ar","Argon"],
    [4,1,19,"K","Potassium"],[4,2,20,"Ca","Calcium"],[4,3,21,"Sc","Scandium"],[4,4,22,"Ti","Titanium"],[4,5,23,"V","Vanadium"],[4,6,24,"Cr","Chromium"],[4,7,25,"Mn","Manganese"],[4,8,26,"Fe","Iron"],[4,9,27,"Co","Cobalt"],[4,10,28,"Ni","Nickel"],[4,11,29,"Cu","Copper"],[4,12,30,"Zn","Zinc"],[4,13,31,"Ga","Gallium"],[4,14,32,"Ge","Germanium"],[4,15,33,"As","Arsenic"],[4,16,34,"Se","Selenium"],[4,17,35,"Br","Bromine"],[4,18,36,"Kr","Krypton"],
    [5,1,37,"Rb","Rubidium"],[5,2,38,"Sr","Strontium"],[5,3,39,"Y","Yttrium"],[5,4,40,"Zr","Zirconium"],[5,5,41,"Nb","Niobium"],[5,6,42,"Mo","Molybdenum"],[5,7,43,"Tc","Technetium"],[5,8,44,"Ru","Ruthenium"],[5,9,45,"Rh","Rhodium"],[5,10,46,"Pd","Palladium"],[5,11,47,"Ag","Silver"],[5,12,48,"Cd","Cadmium"],[5,13,49,"In","Indium"],[5,14,50,"Sn","Tin"],[5,15,51,"Sb","Antimony"],[5,16,52,"Te","Tellurium"],[5,17,53,"I","Iodine"],[5,18,54,"Xe","Xenon"],
    [6,1,55,"Cs","Caesium"],[6,2,56,"Ba","Barium"],[6,3,57,"La","Lanthanum"],[6,4,72,"Hf","Hafnium"],[6,5,73,"Ta","Tantalum"],[6,6,74,"W","Tungsten"],[6,7,75,"Re","Rhenium"],[6,8,76,"Os","Osmium"],[6,9,77,"Ir","Iridium"],[6,10,78,"Pt","Platinum"],[6,11,79,"Au","Gold"],[6,12,80,"Hg","Mercury"],[6,13,81,"Tl","Thallium"],[6,14,82,"Pb","Lead"],[6,15,83,"Bi","Bismuth"],[6,16,84,"Po","Polonium"],[6,17,85,"At","Astatine"],[6,18,86,"Rn","Radon"],
    [7,1,87,"Fr","Francium"],[7,2,88,"Ra","Radium"],[7,3,89,"Ac","Actinium"],[7,4,104,"Rf","Rutherfordium"],[7,5,105,"Db","Dubnium"],[7,6,106,"Sg","Seaborgium"],[7,7,107,"Bh","Bohrium"],[7,8,108,"Hs","Hassium"],[7,9,109,"Mt","Meitnerium"],[7,10,110,"Ds","Darmstadtium"],[7,11,111,"Rg","Roentgenium"],[7,12,112,"Cn","Copernicium"],[7,13,113,"Nh","Nihonium"],[7,14,114,"Fl","Flerovium"],[7,15,115,"Mc","Moscovium"],[7,16,116,"Lv","Livermorium"],[7,17,117,"Ts","Tennessine"],[7,18,118,"Og","Oganesson"],
    // Lanthanides (row 9 visually)
    [9,4,58,"Ce","Cerium"],[9,5,59,"Pr","Praseodymium"],[9,6,60,"Nd","Neodymium"],[9,7,61,"Pm","Promethium"],[9,8,62,"Sm","Samarium"],[9,9,63,"Eu","Europium"],[9,10,64,"Gd","Gadolinium"],[9,11,65,"Tb","Terbium"],[9,12,66,"Dy","Dysprosium"],[9,13,67,"Ho","Holmium"],[9,14,68,"Er","Erbium"],[9,15,69,"Tm","Thulium"],[9,16,70,"Yb","Ytterbium"],[9,17,71,"Lu","Lutetium"],
    // Actinides (row 10 visually)
    [10,4,90,"Th","Thorium"],[10,5,91,"Pa","Protactinium"],[10,6,92,"U","Uranium"],[10,7,93,"Np","Neptunium"],[10,8,94,"Pu","Plutonium"],[10,9,95,"Am","Americium"],[10,10,96,"Cm","Curium"],[10,11,97,"Bk","Berkelium"],[10,12,98,"Cf","Californium"],[10,13,99,"Es","Einsteinium"],[10,14,100,"Fm","Fermium"],[10,15,101,"Md","Mendelevium"],[10,16,102,"No","Nobelium"],[10,17,103,"Lr","Lawrencium"],
  ];

  function heatClass(count, maxCount) {
    if (!count) return "heat-0";
    const ratio = count / maxCount;
    if (ratio > 0.6)  return "heat-6";
    if (ratio > 0.35) return "heat-5";
    if (ratio > 0.2)  return "heat-4";
    if (ratio > 0.1)  return "heat-3";
    if (ratio > 0.03) return "heat-2";
    return "heat-1";
  }

  function render() {
    const container = document.getElementById("pt-container");
    if (!container) return;

    // PT_DATA is injected by the template as [{symbol, count}, ...]
    const ptData = (typeof PT_DATA !== "undefined") ? PT_DATA : [];
    const countMap = {};
    ptData.forEach(r => {
      // symbol might be like "Cu^[2+]" — extract base symbol
      const base = (r.symbol || "").replace(/[\^[\]0-9+\-]/g, "").replace(/\s/g, "");
      countMap[base] = (countMap[base] || 0) + r.count;
    });
    const maxCount = Math.max(...Object.values(countMap), 1);

    let html = `<div class="pt-grid" style="grid-template-rows:repeat(10,1fr)">`;

    for (const [row, col, z, sym, name] of ELEMENTS) {
      const cnt = countMap[sym] || 0;
      const heat = heatClass(cnt, maxCount);
      const tip = `${name} (${sym}) — ${cnt} entries`;
      html += `<div class="pt-cell ${heat}" style="grid-row:${row};grid-column:${col}"
                    title="${tip}" data-symbol="${sym}">
        <span class="number">${z}</span>
        <span class="symbol">${sym}</span>
      </div>`;
    }

    // Labels for lanthanide/actinide rows
    html += `<div class="pt-cell empty" style="grid-row:9;grid-column:1;font-size:.6rem;justify-content:flex-end">Ln</div>`;
    html += `<div class="pt-cell empty" style="grid-row:10;grid-column:1;font-size:.6rem;justify-content:flex-end">An</div>`;
    html += `</div>`;

    // Legend
    html += `<div style="display:flex;gap:1rem;align-items:center;flex-wrap:wrap;margin-top:8px">
      <strong style="font-size:.8rem">Coverage:</strong>
      <span class="pt-cell heat-0" style="width:20px;height:20px;display:inline-flex;font-size:.6rem">0</span>
      <span class="pt-cell heat-1" style="width:20px;height:20px;display:inline-flex;font-size:.6rem">low</span>
      <span class="pt-cell heat-3" style="width:20px;height:20px;display:inline-flex;font-size:.6rem">med</span>
      <span class="pt-cell heat-5" style="width:20px;height:20px;display:inline-flex;font-size:.6rem">high</span>
      <span class="pt-cell heat-6" style="width:20px;height:20px;display:inline-flex;font-size:.6rem">max</span>
    </div>`;

    container.innerHTML = html;

    // Click handler: navigate to metals page filtered by symbol
    container.querySelectorAll(".pt-cell[data-symbol]").forEach(cell => {
      cell.addEventListener("click", () => {
        const sym = cell.dataset.symbol;
        const url = `/metals?q=${encodeURIComponent(sym)}`;
        window.location.href = (typeof window.__pfx__ === "function")
          ? window.__pfx__(url)
          : url;
      });
    });
  }

  // Run when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
})();
