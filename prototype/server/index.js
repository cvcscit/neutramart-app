// Mock backend for the NutraSmart chat-first UI prototype.
// Mimics the real endpoints (/api/analyze, /api/chat, /api/weekly-summary,
// /api/nutrition/summary) with canned, slightly-randomized data so the UI can be
// felt end-to-end without touching real Bedrock/S3.
import express from "express";
import cors from "cors";

const app = express();
app.use(cors());
app.use(express.json({ limit: "15mb" }));
app.use((req, _res, next) => { console.log(`${new Date().toISOString()} ${req.method} ${req.url}`); next(); });

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

// A few plausible food analyses to rotate through.
const SAMPLES = [
  {
    description: "Masala chai with a bowl of granola and mixed berries",
    weight: "320 g", calories: "410 kcal", protein: "11 g", carbs: "62 g",
    fat: "13 g", fiber: "7 g", sugar: "24 g",
    dishes: [
      { name: "Masala Chai", servingSize: "1 cup", calories: 120, protein: 3, carbs: 14, fat: 4 },
      { name: "Granola & Berries", servingSize: "1 bowl", calories: 290, protein: 8, carbs: 48, fat: 9 },
    ],
    micronutrients: { iron: "2.4 mg", calcium: "180 mg", vitamin_c: "22 mg", vitamin_d: "1 mcg", magnesium: "48 mg", potassium: "310 mg" },
    summary: "A balanced breakfast, a little high in added sugar.",
    recommendation: "Great fiber start — consider unsweetened granola to cut sugar.",
  },
  {
    description: "Grilled paneer salad with chickpeas and olive oil dressing",
    weight: "380 g", calories: "520 kcal", protein: "27 g", carbs: "34 g",
    fat: "30 g", fiber: "11 g", sugar: "8 g",
    dishes: [
      { name: "Grilled Paneer", servingSize: "120 g", calories: 280, protein: 18, carbs: 6, fat: 22 },
      { name: "Chickpea Salad", servingSize: "1 bowl", calories: 240, protein: 9, carbs: 28, fat: 8 },
    ],
    micronutrients: { iron: "4.1 mg", calcium: "320 mg", vitamin_c: "18 mg", vitamin_d: "0.4 mcg", magnesium: "72 mg", potassium: "540 mg" },
    summary: "Protein- and fiber-rich, well balanced.",
    recommendation: "Excellent protein. Watch total fat if you're targeting a deficit.",
  },
  {
    description: "Two rotis with dal tadka and a side of curd",
    weight: "410 g", calories: "480 kcal", protein: "19 g", carbs: "68 g",
    fat: "14 g", fiber: "12 g", sugar: "6 g",
    dishes: [
      { name: "Roti (x2)", servingSize: "2 pieces", calories: 220, protein: 7, carbs: 42, fat: 4 },
      { name: "Dal Tadka", servingSize: "1 bowl", calories: 190, protein: 10, carbs: 22, fat: 7 },
      { name: "Curd", servingSize: "100 g", calories: 70, protein: 2, carbs: 4, fat: 3 },
    ],
    micronutrients: { iron: "3.6 mg", calcium: "240 mg", vitamin_c: "3 mg", vitamin_d: "0.2 mcg", magnesium: "66 mg", potassium: "420 mg" },
    summary: "Classic balanced Indian meal, good fiber.",
    recommendation: "Add a vegetable to lift vitamin C and micronutrient variety.",
  },
];

// POST /api/analyze — pretend to run vision analysis on an uploaded photo.
app.post("/api/analyze", async (req, res) => {
  await wait(1400);
  res.json(pick(SAMPLES));
});

// POST /api/chat — canned, keyword-aware assistant replies.
app.post("/api/chat", async (req, res) => {
  const msg = (req.body?.message || "").toLowerCase();
  await wait(900);
  let reply;
  if (/deficien|mineral|iron|vitamin|supplement/.test(msg)) {
    reply =
      "Looking at your last few weeks, your **iron** and **vitamin D** trend a bit low. " +
      "Try adding spinach, lentils, or pumpkin seeds for iron, and a little sun or fortified milk for vitamin D. " +
      "A low-dose vitamin D3 supplement could help — but check with your doctor first. 💊";
  } else if (/week|summary|how.*eat|trend/.test(msg)) {
    reply =
      "This week you averaged **1,980 kcal/day** with a solid protein intake (avg 82 g). " +
      "Fiber is trending up 👍. Sugar spiked on Wednesday — mostly from that dessert. Want the full breakdown?";
  } else if (/protein/.test(msg)) {
    reply = "You're averaging ~82 g of protein a day — right on track for your goal. Paneer and dal are doing the heavy lifting. 💪";
  } else if (/hi|hello|hey/.test(msg)) {
    reply = "Hey! 👋 Snap a photo of your meal or ask me anything about your nutrition.";
  } else {
    reply =
      "Got it! Based on your recent meals, you're eating pretty balanced. " +
      "Snap a photo of your next meal and I'll break down the nutrition for you.";
  }
  res.json({ reply });
});

// GET /api/weekly-summary — canned 2-month style summary text.
app.get("/api/weekly-summary", (_req, res) => {
  res.json({
    summary:
      "NUTRITIONAL ANALYSIS\nAvg 1,980 kcal/day • Protein 82g • Carbs 210g • Fat 68g\n\n" +
      "MINERAL & VITAMIN DEFICIENCIES\nIron and Vitamin D trend low.\n\n" +
      "SUPPLEMENT RECOMMENDATIONS\nConsider Vitamin D3 (1000 IU) and iron-rich foods. Consult a doctor.",
  });
});

// GET /api/nutrition/summary — weekly calories + macros for the dashboard panel.
app.get("/api/nutrition/summary", (_req, res) => {
  res.json({
    week: [
      { day: "Mon", calories: 1850 },
      { day: "Tue", calories: 2100 },
      { day: "Wed", calories: 2320 },
      { day: "Thu", calories: 1760 },
      { day: "Fri", calories: 1990 },
      { day: "Sat", calories: 2210 },
      { day: "Sun", calories: 1680 },
    ],
    macros: { protein: 82, carbs: 210, fat: 68 },
    streak: 12,
  });
});

const PORT = process.env.PORT || 5050;
app.listen(PORT, () => console.log(`NutraSmart prototype API on http://localhost:${PORT}`));
