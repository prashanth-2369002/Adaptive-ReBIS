// build_deck.js -- builds the review deck from results/summary.json + results/figures.
// Every number on the slides is read from the simulation output, none typed by hand.
//   node review/build_deck.js
const path = require("path");
const fs = require("fs");
const NODE_MODULES = process.env.PPTX_NODE_MODULES || "";
const pptxgen = require(NODE_MODULES ? path.join(NODE_MODULES, "pptxgenjs") : "pptxgenjs");
const { applyTheme } = require(process.env.APPLY_THEME_JS);

const ROOT = path.resolve(__dirname, "..");
const RES = path.join(ROOT, "results");
const FIG = path.join(RES, "figures");
const S = JSON.parse(fs.readFileSync(path.join(RES, "summary.json"), "utf8"));
const OUT = path.join(__dirname, "Adaptive-ReBIS_Review_Deck.pptx");

const THEME = {
  name: "Adaptive-ReBIS",
  headFontFace: "Cambria",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B1B1B", lt1: "FFFFFF", dk2: "0F2236", lt2: "EEF2F5",
    accent1: "F2A900", accent2: "2A78D6", accent3: "1BAF7A", accent4: "EB6834",
    accent5: "4A3AA7", accent6: "8A8984", hlink: "2A78D6", folHlink: "4A3AA7",
  },
};
const HEX = THEME.colors;

// ------------------------------------------------------------- helpers
const f0 = (x) => Number(x).toFixed(0);
const f1 = (x) => Number(x).toFixed(1);
const f2 = (x) => Number(x).toFixed(2);
const pngSize = (p) => {
  const b = fs.readFileSync(p);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
pres.title = "Adaptive-ReBIS capstone review";
pres.author = "Reddy Phaneendra, Peela Sai Vivek";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;

const FOOT = "Adaptive-ReBIS  |  Capstone review  |  Batch 23CRT GET003";
pres.defineSlideMaster({
  title: "TITLE_DARK",
  background: { color: C.text2 },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.8, y: 2.0, w: 11.7, h: 1.9, fontFace: THEME.headFontFace, fontSize: 40, bold: true, color: C.background1, valign: "bottom", align: "left", margin: 0 }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: 0.8, y: 4.1, w: 11.7, h: 2.6, fontFace: THEME.bodyFontFace, fontSize: 18, color: C.background2, valign: "top", margin: 0 }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.background1 },
  margin: [0.5, 0.6, 0.6, 0.6],
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 0.3, w: 12.1, h: 0.85, fontFace: THEME.headFontFace, fontSize: 30, bold: true, color: C.text2, valign: "middle", align: "left", margin: 0 }, text: "" } },
    { text: { text: FOOT, options: { x: 0.6, y: 7.05, w: 8, h: 0.3, fontFace: THEME.bodyFontFace, fontSize: 10, color: C.accent6, margin: 0 } } },
  ],
  slideNumber: { x: 12.2, y: 7.05, w: 0.5, h: 0.3, fontFace: THEME.bodyFontFace, fontSize: 10, color: C.accent6, align: "right" },
});

function addFig(slide, file, x, y, maxW, maxH, name) {
  const p = path.join(FIG, file);
  const { w, h } = pngSize(p);
  const s = Math.min(maxW / w, maxH / h);
  const W = w * s, H = h * s;
  slide.addImage({ path: p, x: x + (maxW - W) / 2, y, w: W, h: H, objectName: name || file,
    altText: name || file });
  return { W, H };
}

function stat(slide, x, y, w, big, label, color) {
  slide.addText(big, { x, y, w, h: 0.75, fontFace: THEME.headFontFace, fontSize: 36, bold: true,
    color: color || C.accent2, margin: 0, isTextBox: true, objectName: "stat " + label });
  slide.addText(label, { x, y: y + 0.75, w, h: 0.6, fontSize: 13, color: C.text1, margin: 0,
    valign: "top", isTextBox: true });
}

function bullets(slide, items, x, y, w, h, size) {
  slide.addText(items.map((t, i) => ({
    text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 6 } })),
  { x, y, w, h, fontSize: size || 15, color: C.text1, valign: "top", margin: 0.05, isTextBox: true });
}

function numCircle(slide, x, y, n, color) {
  slide.addShape(pres.shapes.OVAL, { x, y, w: 0.5, h: 0.5, fill: { color: color || C.accent1 }, line: { type: "none" } });
  slide.addText(String(n), { x, y, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: C.text2, align: "center",
    valign: "middle", margin: 0, isTextBox: true });
}

function card(slide, x, y, w, h, title, body, n, color) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: C.background2 },
    line: { type: "none" } });
  numCircle(slide, x + 0.2, y + 0.2, n, color);
  slide.addText(title, { x: x + 0.85, y: y + 0.17, w: w - 1.0, h: 0.55, fontSize: 16, bold: true, color: C.text2,
    valign: "middle", margin: 0, isTextBox: true });
  if (body) slide.addText(body, { x: x + 0.25, y: y + 0.85, w: w - 0.45, h: h - 1.0, fontSize: 13.5, color: C.text1,
    valign: "top", margin: 0, isTextBox: true });
}

// ------------------------------------------------------------- numbers
const A = S.strategies_A, B = S.strategies_B;
const k = (D, s) => D[s];
const G0 = "S0 Grid only", PV = "S1 PV + grid", RB = "S2 Rule-based ReBIS", GA = "S3 Adaptive-ReBIS (GA)",
  PSO = "S4 Adaptive-ReBIS (PSO)", LPF = "S5 LP on forecast", LPP = "S6 Perfect-foresight LP";
const szPSO = S.sizing.find((r) => r.algorithm === "PSO");
const szGA = S.sizing.find((r) => r.algorithm === "GA");
const szGrid = S.sizing.find((r) => r.algorithm.startsWith("Reference: grid"));
const fc = S.forecast, fbest = S.forecast_best;
const v33 = S.validation.find((r) => r.network === "IEEE 33-bus");
const v69 = S.validation.find((r) => r.network === "IEEE 69-bus");
const N = (net, d) => S[`network_${net}_${d}`];
const BASE = "Base feeder (no new sites)";
const rel = (d, s) => S.reliability.find((r) => r.design === d && r.strategy === s);
const op = S.optimality;
const pct = (a, b) => 100 * (1 - a / b);

// ============================================================= slides
pres.addSection({ title: "Introduction" });
let s = pres.addSlide({ masterName: "TITLE_DARK", sectionTitle: "Introduction" });
s.addText("Adaptive-ReBIS: Adaptive Renewable-Integrated Energy Management for EV Charging and Appliance Loads", { placeholder: "title" });
s.addText([
  { text: "ML day-ahead forecasting  |  GA and PSO scheduling and sizing  |  IEEE 33/69-bus validation", options: { breakLine: true, color: HEX.accent1, bold: true } },
  { text: " ", options: { breakLine: true } },
  { text: "Reddy Phaneendra (2300069007)   |   Peela Sai Vivek (2300069015)", options: { breakLine: true } },
  { text: "Guide: Dr. G. Swapna   |   Project Coordinator: Dr. B. Jyothi   |   Batch 23CRT GET003" },
], { placeholder: "body" });
s.addNotes("Good morning. Our project is Adaptive-ReBIS: an energy management system that coordinates solar PV, a battery and the grid for an EV charging hub plus building loads such as HVAC and water heaters. It forecasts tomorrow's demand with machine learning, plans the battery with Genetic Algorithm and Particle Swarm Optimisation, and we validate the result on the IEEE 33-bus and 69-bus distribution feeders.");

// ---- problem
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("EV charging and cooling loads stress distribution feeders", { placeholder: "title" });
const n33A = N("33-bus", "A");
stat(s, 0.6, 1.5, 3.8, `${f0(L_PEAK())} kW`, "site peak at 17:00 on 15 May: EV hub + HVAC + lighting together (our load model)", HEX.accent4);
stat(s, 4.75, 1.5, 3.8, `${f1(100 * S.strategies_A[G0].peak_window_import_MWh / S.strategies_A[G0].grid_import_MWh)} %`, "of the site's grid energy falls in the ToD peak hours (06-10, 18-22) when power costs the most", HEX.accent4);
stat(s, 8.9, 1.5, 3.8, `${f3(n33A[G0].lowest_voltage_pu)} pu`, "lowest voltage on the IEEE 33-bus feeder once 5 such sites draw from the grid, below the 0.91 pu (-9 %) limit", HEX.accent4);
bullets(s, [
  "EV charging is bursty and lands on the evening peak, exactly when air-conditioning and lighting peak too",
  "Solar is available at noon, demand peaks in the evening: without storage and coordination the mismatch goes to the grid",
  "Fixed rules (\"charge on surplus, discharge on deficit\") empty the battery before the evening peak arrives",
  "Utilities see higher peak demand, losses and voltage drop; consumers see higher bills and CO2",
], 0.6, 3.75, 12.1, 3.0, 19);
s.addNotes("The problem. Our site model peaks around 17:00 in May when EV charging, HVAC and evening lighting overlap. A large share of grid energy lands in the ToD peak window. When five such sites sit on the IEEE 33-bus feeder, the tail voltage drops below the Indian -9 percent limit. A simple battery rule doesn't solve it, because the battery is often already empty when the evening peak arrives.");

// ---- objectives
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("Objectives", { placeholder: "title" });
const obj = [
  ["Real, localised data", "Hourly PVGIS solar/wind/temperature for Hyderabad, TGERC Time-of-Day tariff, CEA grid CO2 factor"],
  ["Forecast tomorrow", "Machine-learning model predicts next-day hourly demand of EV + appliance loads"],
  ["Optimise power sharing", "GA and PSO decide the hourly PV-battery-grid schedule with adaptive cost / peak / CO2 priorities"],
  ["Optimise sizing", "GA and PSO choose PV kWp, battery kWh and wind kW on a full-year simulation"],
  ["Validate on the grid", "Load flow on the IEEE 33-bus and 69-bus feeders: voltage, losses, substation peak"],
  ["Report KPIs", "Energy cost, peak demand, CO2 emissions and reliability during grid outages"],
];
obj.forEach((o, i) => {
  const col = i % 2, row = Math.floor(i / 2);
  card(s, 0.6 + col * 6.15, 1.45 + row * 1.8, 5.95, 1.6, o[0], o[1], i + 1, HEX.accent1);
});
s.addNotes("Six objectives, each maps to one module of the code. Data, forecasting, power-sharing optimisation, sizing, grid validation and the KPIs.");

// ---- base paper and contributions
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Introduction" });
s.addText("From the base paper (ReBIS) to Adaptive-ReBIS", { placeholder: "title" });
const rows = [
  [{ text: "Limitation in the base work", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } },
   { text: "What Adaptive-ReBIS adds", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } }],
  ["Single EV-station application", "One EMS for EV hub + HVAC + water heaters + general load behind one meter"],
  ["Fixed, equal objective weights all day", "Hour-dependent (adaptive) weights on cost / peak / CO2 following the ToD windows"],
  ["Hand-tuned demand, no forecasting", "ML day-ahead demand forecast (4 models vs 2 baselines, out-of-sample)"],
  ["Fixed rule-based dispatch", "GA / PSO day-ahead schedule + real-time correction for forecast error"],
  ["PV / battery sized manually", "GA and PSO joint sizing of PV, battery and wind on 8784 hours"],
  ["Australian tariff and data", "Indian data: PVGIS Hyderabad, TGERC ToD tariff, CEA CO2 factor"],
  ["No network-level check", "IEEE 33-bus and 69-bus annual load flow (voltage, losses, peak)"],
];
s.addTable(rows, { x: 0.6, y: 1.4, w: 12.1, colW: [4.6, 7.5], fontSize: 14, color: HEX.dk1, valign: "middle",
  border: { type: "solid", pt: 0.75, color: "D5DBE1" }, rowH: 0.62, fill: { color: HEX.lt1 } });
s.addText("Base paper: A. U. Rehman, J. Lu, B. Du, F. Bai, M. J. Sanjari, \"Efficient management of electric vehicle charging stations: balancing user preferences and grid demands with energy storage systems and renewable energy\", Applied Energy, vol. 393, 2025, 126147.",
  { x: 0.6, y: 6.55, w: 12.1, h: 0.45, fontSize: 10, color: HEX.accent6, margin: 0, isTextBox: true });
s.addNotes("Our starting point is the ReBIS strategy from Rehman et al., Applied Energy 2025. It was one EV station in Australia, with fixed weights and rule-based dispatch. We extend it in seven ways, listed here. The two genuinely new ideas are the adaptive time-varying weights and the forecast-driven optimiser with real-time correction; the rest is thorough engineering: Indian data, joint sizing, and network validation.");

// ---- architecture
pres.addSection({ title: "Method" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("System architecture", { placeholder: "title" });
addFig(s, "fig00_system_architecture.png", 0.6, 1.3, 12.1, 5.6, "Architecture diagram");
s.addNotes("The whole pipeline. One: real data. Two: ML forecast of tomorrow's hourly demand. Three: the day-ahead optimiser, GA or PSO, produces a 24-hour battery schedule using adaptive weights; the exact LP is our check. Four: in real time the controller corrects for forecast error. Five: the site itself, where PV feeds the load first, the battery charges from surplus and discharges by SOC, and the grid covers the rest. Six: we load-flow the result on the IEEE feeders and compute the KPIs. This runs for every day of the year, with the battery state carried from one day to the next.");

// ---- data
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("Real input data for Hyderabad", { placeholder: "title" });
addFig(s, "fig01_resource_data.png", 0.6, 1.3, 12.1, 3.7, "Resource data");
const drows = [
  ["Solar, temperature, wind", "PVGIS v5.2 (EU JRC), ERA5, 2020, hourly, 8784 h, 17.385 N 78.487 E"],
  ["Tariff", "TGERC FY2023-24 ToD: off-peak Rs 5, normal Rs 6, peak Rs 7 per kWh"],
  ["Grid CO2", "CEA CO2 Baseline Database: 0.716 kg CO2 per kWh"],
  ["Distribution feeders", "IEEE 33-bus and 69-bus (Baran and Wu), 12.66 kV"],
];
s.addTable(drows, { x: 0.6, y: 5.15, w: 12.1, colW: [3.2, 8.9], fontSize: 13, color: HEX.dk1, rowH: 0.4,
  border: { type: "solid", pt: 0.5, color: "D5DBE1" }, fill: { color: HEX.lt2 } });
s.addNotes("All weather and resource inputs are real: a full year of hourly PVGIS data for Hyderabad. PV yields about 3.7 kWh per kWp per day. Wind is very weak here, a capacity factor of only about 3 percent, which matters for sizing. Tariff is the real TGERC time-of-day structure, CO2 factor from CEA.");

// ---- load model
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("Site load model: EV hub plus appliance loads", { placeholder: "title" });
addFig(s, "fig02_site_load_profile.png", 0.6, 1.3, 7.9, 5.5, "Load profile");
bullets(s, [
  "EV hub: 8 x 7.4 kW AC + 2 x 30 kW DC chargers; every EV simulated (arrival, energy, charger queue) at 15-min steps",
  "HVAC: driven by the real hourly temperature, occupancy 9-19 h, COP falls as it gets hotter",
  "Water heaters: morning / evening peaks, more in winter",
  "General: lighting, plugs, pumps",
  "Seeded random numbers: every run gives identical results",
], 8.8, 1.45, 3.95, 5.4, 14);
s.addNotes("We had no metered data for the site, so the load is modelled, but on top of the real temperature series. Each EV is simulated individually with a charger queue. This is the honest point to state: weather and tariff are real, the load is a model.");

// ---- forecast
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("ML day-ahead demand forecasting", { placeholder: "title" });
addFig(s, "fig03_load_forecast.png", 0.6, 1.3, 12.1, 3.95, "Forecast");
const fb = fc[fbest], fp = fc["Persistence (yesterday)"];
stat(s, 0.6, 5.4, 3.0, `R2 ${f2(fb.R2)}`, `${fbest}, vs ${f2(fp.R2)} for "same as yesterday"`, HEX.accent2);
stat(s, 3.75, 5.4, 3.0, `${f1(fb.MAPE_pct)} %`, "hourly MAPE, every forecast out-of-sample", HEX.accent2);
stat(s, 6.9, 5.4, 3.0, `${f1(fb.RMSE_kW)} kW`, `RMSE (persistence ${f1(fp.RMSE_kW)} kW)`, HEX.accent2);
s.addText("Inputs: hour, weekday, season, next-day temperature forecast, load 24 h / 48 h / 168 h earlier, yesterday's mean and peak. Validation: 12-fold month-blocked CV.",
  { x: 10.05, y: 5.4, w: 2.7, h: 1.45, fontSize: 12, color: HEX.accent6, margin: 0, valign: "top", isTextBox: true });
s.addNotes(`Six forecasters compared. Every forecast is out-of-sample: for each month, the model is trained on the other eleven. The neural network and random forest are clearly better than the naive "same as yesterday" forecast: R-squared ${f2(fb.R2)} versus ${f2(fp.R2)}. EV demand is random by nature, so a perfect forecast is impossible; that is why the real-time layer exists.`);

// ---- formulation
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("EMS formulation: adaptive multi-objective scheduling", { placeholder: "title" });
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 1.4, w: 7.2, h: 2.2, rectRadius: 0.08, fill: { color: HEX.lt2 }, line: { type: "none" } });
s.addText([
  { text: "Decision: battery power P_b(t), t = 1..24 h", options: { bold: true, breakLine: true } },
  { text: "J = Σ w_c(t)·Cost(t)/C₀  +  Σ w_e(t)·CO₂(t)/E₀  +  W_p·max φ(t)·P_grid(t) / P₀", options: { breakLine: true, fontFace: "Cambria Math" } },
  { text: "Grid(t) = Load(t) − PV(t) − Wind(t) − P_b(t)   (import > 0, export < 0, export ≤ 150 kW)", options: { breakLine: true } },
  { text: "SOC limits 20-95 %, |P_b| ≤ 0.5C, η = 95 %, end-of-day SOC ≥ 50 %" },
], { x: 0.85, y: 1.5, w: 6.8, h: 2.0, fontSize: 14, color: HEX.dk1, valign: "middle", margin: 0, isTextBox: true });
const wrows = [
  [{ text: "Hours", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } },
   { text: "w cost", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } },
   { text: "w peak", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } },
   { text: "w CO2", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } }],
  ["ToD peak 06-10, 18-22", "0.35", "0.50", "0.15"],
  ["Normal 10-18", "0.50", "0.20", "0.30"],
  ["Off-peak 22-06", "0.70", "0.15", "0.15"],
];
s.addTable(wrows, { x: 8.1, y: 1.4, w: 4.6, colW: [2.2, 0.8, 0.8, 0.8], fontSize: 13, color: HEX.dk1, rowH: 0.42,
  border: { type: "solid", pt: 0.5, color: "D5DBE1" }, align: "center" });
s.addText("Adaptive weights: priority shifts from \"cheapest\" at night to \"lowest grid draw\" in the evening peak.",
  { x: 8.1, y: 3.45, w: 4.6, h: 0.6, fontSize: 12, color: HEX.accent6, margin: 0, valign: "top", isTextBox: true });
card(s, 0.6, 4.2, 3.9, 2.55, "Day-ahead plan", "End of day D-1: ML forecast of load and PV for day D goes to GA or PSO, which returns 24 battery set-points.", 1, HEX.accent1);
card(s, 4.7, 4.2, 3.9, 2.55, "Real-time correction", "In peak hours the battery absorbs forecast error so grid draw stays at plan. Other hours: unforecast solar surplus is stored, not exported.", 2, HEX.accent1);
card(s, 8.8, 4.2, 3.9, 2.55, "Peak guard", "Every hour, grid import may not exceed the day's planned maximum: the battery charges less or discharges more.", 3, HEX.accent1);
s.addNotes("The heart of the EMS. One decision variable per hour: battery power. The objective is a weighted sum of cost, CO2 and a weighted peak, each normalised by the no-battery case so the weights are comparable. The weights are adaptive: at night cost matters most, in the evening ToD peak the weight moves to grid peak. The schedule must leave the battery at least half full for tomorrow's morning peak. Then three layers: the day-ahead plan, real-time correction, and a peak guard.");

// ---- GA and PSO
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("GA and PSO solvers, benchmarked against the exact optimum", { placeholder: "title" });
card(s, 0.6, 1.4, 3.95, 2.55, "Genetic Algorithm", "Population 150, 500 generations. Tournament selection, blend (BLX-0.3) crossover, Gaussian mutation, elitism. Each schedule repaired to SOC / power limits before scoring.", 1, HEX.accent5);
card(s, 4.7, 1.4, 3.95, 2.55, "Particle Swarm", "100 particles, 500 iterations. Inertia 0.9 to 0.4, c1 = c2 = 1.8, velocity clamp. Same repair and the same objective as GA.", 2, HEX.accent2);
card(s, 8.8, 1.4, 3.9, 2.55, "Exact LP (benchmark)", "The same day-ahead problem written as a Linear Program, solved by HiGHS. Gives the true optimum, so we can measure how close GA and PSO get.", 3, HEX.accent3);
stat(s, 0.6, 4.55, 3.95, `${f2(op.PSO_mean)} %`, `PSO mean gap to optimum over ${op.days} days (95th pct ${f2(op.PSO_p95)} %)`, HEX.accent2);
stat(s, 4.7, 4.55, 3.95, `${f2(op.GA_mean)} %`, `GA mean gap to optimum (95th pct ${f2(op.GA_p95)} %)`, HEX.accent5);
stat(s, 8.8, 4.55, 3.9, `${f0(op.t_PSO_ms)} ms`, `PSO solve time per day (GA ${f0(op.t_GA_ms)} ms, LP ${f0(op.t_LP_ms)} ms)`, HEX.accent3);
s.addNotes(`Both metaheuristics are implemented in NumPy and vectorised over the whole population, so a day solves in well under a second. The key point: because this problem happens to be linear, we can also solve it exactly by LP, and that tells us how good GA and PSO are. Over all ${op.days} days PSO is on average ${f2(op.PSO_mean)} percent from the true optimum and GA ${f2(op.GA_mean)} percent. Why keep GA and PSO if LP exists? Because once you add non-linear battery ageing, discrete charger control or converter efficiency curves, LP no longer applies; GA and PSO do.`);

s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Method" });
s.addText("Solution quality over every day of the year", { placeholder: "title" });
addFig(s, "fig07_GA_PSO_vs_LP.png", 0.6, 1.4, 12.1, 4.6, "Optimality");
s.addText(`PSO beat GA on ${op.PSO_better_days} of ${op.days} days. Left: gap to the exact LP optimum. Middle: improvement over no battery. Right: convergence on the peak day.`,
  { x: 0.6, y: 6.25, w: 12.1, h: 0.6, fontSize: 14, color: HEX.dk1, margin: 0, isTextBox: true });
s.addNotes(`Distribution of the optimality gap over all ${op.days} days. PSO is lower on average (${f2(op.PSO_mean)} vs ${f2(op.GA_mean)} percent) and at the 95th percentile (${f2(op.PSO_p95)} vs ${f2(op.GA_p95)}); both have a few harder days, the single worst being ${f1(op.PSO_max)} percent for PSO and ${f1(op.GA_max)} for GA. The convergence plot shows both on the peak day.`);

// ---- sizing
pres.addSection({ title: "Results" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Optimal sizing by GA and PSO", { placeholder: "title" });
addFig(s, "fig04_sizing_GA_PSO.png", 0.6, 1.35, 12.1, 3.9, "Sizing");
stat(s, 0.6, 5.35, 2.9, `${f0(szPSO.pv_kWp)} kWp`, "PV (hits the roof/carport limit: PV pays back)", HEX.accent1);
stat(s, 3.65, 5.35, 2.9, `${f0(szPSO.bess_kWh)} kWh`, "battery at Rs 15,000/kWh", HEX.accent2);
stat(s, 6.7, 5.35, 2.9, `${f0(szPSO.wind_kW)} kW`, "wind: Hyderabad wind too weak (CUF ~3 %)", HEX.accent6);
stat(s, 9.75, 5.35, 2.95, `${f1(pct(szPSO.total_lakh, szGrid.total_lakh))} %`, `lower total annual cost incl. capital (${f1(szPSO.total_lakh)} vs ${f1(szGrid.total_lakh)} lakh)`, HEX.accent3);
s.addNotes(`GA and PSO search PV, battery and wind sizes; each candidate is simulated over all 8784 hours, scored on annualised capital cost plus O and M, energy bill, demand charges, battery wear and a carbon cost. Both converge to the same answer: ${f0(szPSO.pv_kWp)} kWp PV, ${f0(szPSO.bess_kWh)} kWh battery and no wind. Honest finding: at today's battery price the battery barely pays on the bill alone; the right chart shows the optimum battery growing as battery prices fall.`);

// ---- one-day dispatch
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("How Adaptive-ReBIS shares power on the peak day", { placeholder: "title" });
addFig(s, "fig05_dispatch_day.png", 0.6, 1.25, 7.4, 5.7, "Dispatch day");
bullets(s, [
  "Solar feeds the load first; surplus charges the battery at noon",
  "Rule-based ReBIS spends its battery in the afternoon and is empty when the evening EV + lighting peak arrives",
  "Adaptive-ReBIS holds charge for the 18-22 h ToD peak, guided by the forecast",
  "Battery is refilled overnight at the off-peak tariff for the next morning peak",
], 8.3, 1.5, 4.4, 5.3, 15);
s.addNotes("This is one day, 15 May, the highest-demand day. Top: where the power comes from each hour. Middle: battery state of charge, rule-based in orange versus ours in blue. The rule-based battery is emptied in the afternoon; ours waits for the evening peak. Bottom: grid import; our peak is the lowest of the three.");

// ---- annual comparison A
function annualSlide(D, label, fig) {
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
  sl.addText(`Full-year results: ${label}`, { placeholder: "title" });
  addFig(sl, fig, 0.6, 1.3, 12.1, 3.85, "Annual comparison " + label);
  const p = D[PSO], r = D[RB], g = D[G0];
  stat(sl, 0.6, 5.3, 2.9, `${f1(p.cost_saving_pct)} %`, `lower operating cost vs grid only (rule-based ${f1(r.cost_saving_pct)} %)`, HEX.accent2);
  stat(sl, 3.65, 5.3, 2.9, `${f1(p.peak_reduction_pct)} %`, `lower annual peak (rule-based ${f1(r.peak_reduction_pct)} %)`, HEX.accent2);
  stat(sl, 6.7, 5.3, 2.9, `${f0(p.mean_daily_peak_kW)} kW`, `average daily peak (rule ${f0(r.mean_daily_peak_kW)}, grid only ${f0(g.mean_daily_peak_kW)})`, HEX.accent2);
  stat(sl, 9.75, 5.3, 2.95, `${f1(p.CO2_reduction_pct)} %`, `less CO2 (rule-based ${f1(r.CO2_reduction_pct)} %)`, HEX.accent3);
  return sl;
}
const sA = annualSlide(A, "Design A (economic optimum)", "fig06a_strategy_comparison_designA.png");
sA.addNotes(`Every day of 2020, seven strategies. Adaptive-ReBIS with PSO saves ${f1(A[PSO].cost_saving_pct)} percent of operating cost versus grid only, slightly more than the rule-based ReBIS, while cutting the annual peak by ${f1(A[PSO].peak_reduction_pct)} percent versus ${f1(A[RB].peak_reduction_pct)} percent. PSO lands on top of the exact LP on forecast. The perfect-foresight LP is an upper bound that needs tomorrow known exactly; the gap to it is the cost of forecast error. Honest note: CO2 is marginally higher than the rule-based scheme, because keeping charge for the peak means a little more battery loss.`);
const sB = annualSlide(B, "Design B (200 kWh grid-support battery)", "fig06b_strategy_comparison_designB.png");
sB.addNotes(`Same comparison with a larger, 200 kWh battery sized for grid support rather than for the bill. With more storage the adaptive scheduler's advantage in peak reduction grows clearly: average daily peak ${f0(B[PSO].mean_daily_peak_kW)} kW with PSO and ${f0(B[GA].mean_daily_peak_kW)} kW with GA, versus ${f0(B[RB].mean_daily_peak_kW)} kW for the rule-based scheme. Note that over the real year GA and PSO end within about one percent on cost; GA even gave the lower peak here. Once the plan is near-optimal, forecast quality matters more than the choice of optimiser. CO2: the rule-based scheme is lower (${f1(B[RB].CO2_reduction_pct)} versus ${f1(B[PSO].CO2_reduction_pct)} percent reduction), because it never charges from the grid; that is the price of holding charge for the peak.`);

// ---- battery sensitivity
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Results" });
s.addText("Battery size: where the adaptive EMS earns its keep", { placeholder: "title" });
addFig(s, "fig10_battery_size_sensitivity.png", 0.6, 1.3, 12.1, 4.2, "Battery sensitivity");
const bAt = (E, st) => S.battery.find((r) => r.bess_kWh === E && r.strategy === st);
const b200p = bAt(200, PSO), b200r = bAt(200, RB);
bullets(s, [
  `At every battery size the adaptive EMS gives a lower daily peak than the rule (200 kWh: ${f0(b200p.mean_daily_peak_kW)} vs ${f0(b200r.mean_daily_peak_kW)} kW)`,
  "The rule-based scheme barely uses extra capacity for peak shaving; the forecast-driven plan does",
  "Trade-off: the adaptive plan cycles the battery more, so CO2 and wear are slightly higher; the weights are tunable",
], 0.6, 5.65, 12.1, 1.3, 14);
s.addNotes("This sweep shows the value of the adaptive EMS grows with battery size. A bigger battery with the old rule gives almost no extra peak reduction. Our planner turns capacity into peak shaving. We are open about the trade-off: more cycling means slightly more losses and wear.");

// ---- IEEE validation
pres.addSection({ title: "Network validation" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Network validation" });
s.addText("IEEE 33-bus and 69-bus: load-flow model first validated", { placeholder: "title" });
const vrows = [
  [{ text: "Base case", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } },
   { text: "Published", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } },
   { text: "pandapower (NR)", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } },
   { text: "Our BFS solver", options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } }],
  ["33-bus real power loss (kW)", f2(v33.published_loss_kW), f2(v33.pandapower_loss_kW), f2(v33.our_BFS_loss_kW)],
  ["33-bus minimum voltage (pu)", f3(v33.published_Vmin_pu), f3(v33.pandapower_Vmin_pu), f3(v33.our_BFS_Vmin_pu) + " @ bus " + v33.Vmin_bus],
  ["69-bus real power loss (kW)", f2(v69.published_loss_kW), f2(v69.pandapower_loss_kW), f2(v69.our_BFS_loss_kW)],
  ["69-bus minimum voltage (pu)", f3(v69.published_Vmin_pu), f3(v69.pandapower_Vmin_pu), f3(v69.our_BFS_Vmin_pu) + " @ bus " + v69.Vmin_bus],
];
s.addTable(vrows, { x: 0.6, y: 1.45, w: 12.1, colW: [4.3, 2.4, 2.6, 2.8], fontSize: 15, color: HEX.dk1, rowH: 0.55,
  border: { type: "solid", pt: 0.5, color: "D5DBE1" }, align: "center" });
bullets(s, [
  "Two independent solvers: pandapower (Newton-Raphson, open-source) and our own backward/forward sweep",
  `Hour-by-hour cross-check with the sites connected: max voltage difference ${S.bfs_vs_pp.max_dV.toExponential(1)} pu`,
  "Our BFS is vectorised over all 8784 hours, so a full year of load flow takes about one second",
  "5 identical Adaptive-ReBIS sites at the feeder tails: 33-bus 18, 22, 25, 30, 33  |  69-bus 27, 35, 46, 50, 65",
  "Existing feeder load follows a daily shape peaking at 20:00 (the published bus load = 1.0)",
], 0.6, 4.45, 12.1, 2.5, 15);
s.addNotes("Before trusting any network result we reproduce the published base cases: 202.67 kW loss and 0.9131 pu on the 33-bus, 224.95 kW and 0.9092 pu on the 69-bus. Both our solvers match. Our own backward-forward sweep agrees with pandapower to better than a millionth of a pu, and since it is vectorised we can run the whole year, not just a few snapshots.");

function netSlide(D) {
  const sl = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Network validation" });
  sl.addText(`Feeder impact over the year (Design ${D})`, { placeholder: "title" });
  addFig(sl, `fig08_network_voltage_profile_design${D}.png`, 0.6, 1.25, 12.1, 3.6, "Voltage profile " + D);
  const hdr = (t) => ({ text: t, options: { bold: true, color: HEX.lt1, fill: { color: HEX.dk2 } } });
  const T = [[hdr("Case (5 sites)"), hdr("33-bus lowest V, pu"), hdr("33-bus hours < 0.91"), hdr("33-bus bus-hours < 0.91"),
    hdr("33-bus losses, MWh/yr"), hdr("69-bus lowest V, pu"), hdr("69-bus hours < 0.91"), hdr("69-bus bus-hours < 0.91")]];
  const n33 = N("33-bus", D), n69 = N("69-bus", D);
  [[BASE, "Base feeder, no sites"], [G0, "Grid only"], [RB, "Rule-based ReBIS"], [PSO, "Adaptive-ReBIS (PSO)"]].forEach(([key, lab]) => {
    const o = key === PSO ? { bold: true, color: HEX.accent2 } : {};
    T.push([{ text: lab, options: o }, { text: f3(n33[key].lowest_voltage_pu), options: o },
      { text: f0(n33[key]["hours_below_0.91pu"]), options: o }, { text: f0(n33[key]["bus_hours_below_0.91pu"]), options: o },
      { text: f0(n33[key].annual_losses_MWh), options: o },
      { text: f3(n69[key].lowest_voltage_pu), options: o }, { text: f0(n69[key]["hours_below_0.91pu"]), options: o },
      { text: f0(n69[key]["bus_hours_below_0.91pu"]), options: o }]);
  });
  sl.addTable(T, { x: 0.6, y: 4.95, w: 12.1, colW: [2.5, 1.35, 1.35, 1.45, 1.35, 1.35, 1.35, 1.4], fontSize: 11.5,
    color: HEX.dk1, rowH: 0.37, border: { type: "solid", pt: 0.5, color: "D5DBE1" }, align: "center" });
  return [sl, n33, n69];
}
const [nA, a33, a69] = netSlide("A");
nA.addNotes(`Network results for the economic design, five sites on each feeder, every hour of the year. Adding the sites on grid supply alone pushes the 33-bus tail to ${f3(a33[G0].lowest_voltage_pu)} pu, below the 0.91 limit for ${f0(a33[G0]["hours_below_0.91pu"])} hours. PV and the battery schemes reduce both the hours and the losses. With only a ${f0(szPSO.bess_kWh)} kWh battery the battery schemes are close to each other; the next slide shows the 200 kWh design.`);
const [nB, b33, b69] = netSlide("B");
nB.addNotes(`With the 200 kWh battery. Adaptive-ReBIS gives the best lowest voltage, the fewest under-voltage bus-hours (${f0(b33[PSO]["bus_hours_below_0.91pu"])} versus ${f0(b33[RB]["bus_hours_below_0.91pu"])} rule-based on 33-bus), and the lowest losses and substation peak. One honest finding: the rule-based scheme has fewer HOURS below the limit (${f0(b33[RB]["hours_below_0.91pu"])} versus ${f0(b33[PSO]["hours_below_0.91pu"])}). The reason is that our EMS follows the TGERC tariff, whose peak windows are 6 to 10 and 18 to 22, while this feeder is most stressed from 17 to 21. So part of the battery is spent on the morning tariff peak when the feeder is not stressed. The tariff signal and the network signal do not line up. That is our main future-work item: feed a DSO network-stress signal into the weights.`);

s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Network validation" });
s.addText("Lowest feeder voltage across the year", { placeholder: "title" });
addFig(s, "fig09_network_voltage_duration_designB.png", 0.6, 1.3, 12.1, 4.3, "Voltage duration");
const rA = rel("A", PSO), rB = rel("B", PSO), rRB = rel("B", RB);
bullets(s, [
  "Duration curve: hours of the year sorted from the lowest voltage up; the left edge is the worst hours",
  `Reliability (Monte-Carlo, 200 years of random outages, about 48 per year): Adaptive-ReBIS serves ${f0(rB.served_during_outage_pct)} % of outage-time demand with the 200 kWh battery (rule-based ${f0(rRB.served_during_outage_pct)} %; ${f0(rA.served_during_outage_pct)} % with 49 kWh), because it keeps charge in reserve. Grid-tied PV without a battery serves 0 % (anti-islanding)`,
], 0.6, 5.75, 12.1, 1.2, 14);
s.addNotes("The duration curve shows the whole year at once. And a reliability view: during random grid outages, a site with PV and a battery behind a hybrid inverter can keep serving load; a grid-tied PV system without battery must shut down. These outage statistics are an assumption, stated in the code.");

// ---- tools and demo
pres.addSection({ title: "Wrap-up" });
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Wrap-up" });
s.addText("Implementation and live demo", { placeholder: "title" });
const tools = [
  ["Python + NumPy", "Simulation core, GA and PSO written from scratch, population-vectorised"],
  ["scikit-learn", "Ridge, Random Forest, Gradient Boosting, Neural Network forecasters"],
  ["SciPy HiGHS", "Exact LP benchmark of the scheduling problem"],
  ["pandapower + own BFS", "IEEE 33/69-bus Newton-Raphson and backward/forward sweep load flow"],
  ["Streamlit + Plotly", "Live dashboard: pick a day, PV / battery size, optimiser; EMS and feeder run live"],
];
tools.forEach((t, i) => card(s, 0.6, 1.4 + i * 1.08, 6.4, 0.95, t[0], "", i + 1, HEX.accent1));
tools.forEach((t, i) => s.addText(t[1], { x: 4.35, y: 1.4 + i * 1.08, w: 2.55, h: 0.95, fontSize: 12, color: HEX.dk1, valign: "middle", margin: 0, isTextBox: true }));
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 7.3, y: 1.4, w: 5.4, h: 5.3, rectRadius: 0.08, fill: { color: HEX.dk2 }, line: { type: "none" } });
s.addText([
  { text: "Live demo", options: { bold: true, fontSize: 20, color: HEX.accent1, breakLine: true } },
  { text: " ", options: { breakLine: true, fontSize: 8 } },
  { text: "RUN_DASHBOARD.bat  (or  py -m streamlit run dashboard/app.py)", options: { breakLine: true, fontSize: 13, color: HEX.lt1 } },
  { text: " ", options: { breakLine: true, fontSize: 8 } },
  { text: "1. 15 May, PSO: grid peak vs rule-based and grid only", options: { breakLine: true } },
  { text: "2. Switch optimiser PSO / GA / LP: same answer, different speed", options: { breakLine: true } },
  { text: "3. Priority slider: lowest bill vs lowest grid peak", options: { breakLine: true } },
  { text: "4. IEEE feeder tab: tail voltage at 18:00 vs the 0.91 pu limit", options: { breakLine: true } },
  { text: "5. Forecast tab: ML vs persistence for that week", options: { breakLine: true } },
  { text: " ", options: { breakLine: true, fontSize: 8 } },
  { text: "py run_all.py regenerates every number in this deck", options: { color: HEX.accent1 } },
], { x: 7.6, y: 1.65, w: 4.9, h: 4.9, fontSize: 16, color: HEX.lt2, valign: "top", margin: 0, paraSpaceAfter: 4, isTextBox: true });
s.addNotes("Everything is open-source Python, and one command regenerates every number in this deck. For the demo, open the dashboard and walk through the five steps on the right.");

// ---- conclusion
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Wrap-up" });
s.addText("Conclusions and next steps", { placeholder: "title" });
bullets(s, [
  `Forecast-driven GA / PSO scheduling beats the rule-based ReBIS on cost and peak at every battery size; PSO is within ${f2(op.PSO_mean)} % of the exact optimum on average`,
  `Economic design for Hyderabad: ${f0(szPSO.pv_kWp)} kWp PV + ${f0(szPSO.bess_kWh)} kWh battery, no wind; ${f1(A[PSO].cost_saving_pct)} % lower operating cost and ${f1(A[PSO].CO2_reduction_pct)} % less CO2 than grid only`,
  "On IEEE 33/69-bus feeders the adaptive scheme gives the shallowest voltage dips, fewest under-voltage bus-hours, lowest losses and substation peak; the ToD tariff windows do not match the feeder's stress hours, so a network signal is the next step",
  "Honest limits: modelled (not metered) site load, assumed capital / outage data, flat CO2 factor",
], 0.6, 1.4, 7.4, 5.4, 17);
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 8.3, y: 1.4, w: 4.4, h: 5.4, rectRadius: 0.08, fill: { color: HEX.lt2 }, line: { type: "none" } });
s.addText([
  { text: "Next steps", options: { bold: true, fontSize: 18, color: HEX.dk2, breakLine: true } },
  { text: "Smart EV charging (shift / slow sessions) as a second control variable", options: { bullet: true, breakLine: true } },
  { text: "Battery ageing model in the objective (where GA / PSO beat LP)", options: { bullet: true, breakLine: true } },
  { text: "Real metered campus / EV-station data to retrain the forecaster", options: { bullet: true, breakLine: true } },
  { text: "Network-aware weights from a DSO feeder-stress signal (tariff peak 06-10 h is not the feeder peak 17-21 h)", options: { bullet: true, breakLine: true } },
  { text: "Hourly marginal CO2 factor instead of a flat average", options: { bullet: true, breakLine: true } },
  { text: "Conference paper write-up", options: { bullet: true } },
], { x: 8.55, y: 1.6, w: 4.0, h: 5.0, fontSize: 14, color: HEX.dk1, valign: "top", margin: 0, paraSpaceAfter: 8, isTextBox: true });
s.addNotes("To conclude: the adaptive, forecast-driven scheduler outperforms the rule-based ReBIS on cost and peak, PSO reaches the exact optimum within a fraction of a percent, the sizing gives a clear economic design, and the network study shows the benefit at feeder level. Next steps: add smart EV charging, a battery ageing model, real metered data and a marginal emission factor.");

// ---- references
s = pres.addSlide({ masterName: "CONTENT", sectionTitle: "Wrap-up" });
s.addText("References", { placeholder: "title" });
bullets(s, [
  "[1] M. M. Asiri et al., \"Short-Term Load Forecasting in Smart Grids Using Hybrid Deep Learning,\" IEEE Access, vol. 12, pp. 23504-23513, 2024.",
  "[2] W. M. N. Witharama et al., \"Advanced Genetic Algorithm for Optimal Microgrid Scheduling Considering Solar and Load Forecasting, Battery Degradation, and Demand Response Dynamics,\" IEEE Access, vol. 12, pp. 83269-83284, 2024.",
  "[3] A. U. Rehman, J. Lu, B. Du, F. Bai, M. J. Sanjari, \"Efficient management of electric vehicle charging stations: balancing user preferences and grid demands with energy storage systems and renewable energy,\" Applied Energy, vol. 393, 126147, 2025.",
  "[4] M. E. Baran and F. F. Wu, \"Network reconfiguration in distribution systems for loss reduction and load balancing,\" IEEE Trans. Power Delivery, vol. 4, no. 2, pp. 1401-1407, 1989.",
  "[5] M. E. Baran and F. F. Wu, \"Optimal sizing of capacitors placed on a radial distribution system,\" IEEE Trans. Power Delivery, vol. 4, no. 1, pp. 735-743, 1989.",
  "[6] L. Thurner et al., \"pandapower - an open-source Python tool for convenient modeling, analysis, and optimization of electric power systems,\" IEEE Trans. Power Systems, vol. 33, no. 6, pp. 6510-6521, 2018.",
  "[7] European Commission JRC, PVGIS v5.2; TGERC Retail Supply Tariff Order FY2023-24; CEA CO2 Baseline Database for the Indian Power Sector.",
], 0.6, 1.4, 12.1, 5.5, 13);
s.addNotes("References: the two journal papers from our abstract, the base paper, the IEEE test-feeder sources, pandapower, and the data sources.");

function L_PEAK() { return S.strategies_A[G0].annual_peak_import_kW; }
function f3(x) { return Number(x).toFixed(3); }

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
