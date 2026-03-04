from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

doc = Document()

style = doc.styles["Normal"]
style.font.name = "Calibri"
style.font.size = Pt(11)
style.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
style.paragraph_format.space_after = Pt(6)
style.paragraph_format.line_spacing = 1.15

for level in range(1, 4):
    hs = doc.styles[f"Heading {level}"]
    hs.font.name = "Calibri"
    hs.font.color.rgb = RGBColor(0x1A, 0x56, 0x7E)
    hs.font.bold = True
    if level == 1:
        hs.font.size = Pt(26)
        hs.paragraph_format.space_before = Pt(24)
    elif level == 2:
        hs.font.size = Pt(18)
        hs.paragraph_format.space_before = Pt(18)
    else:
        hs.font.size = Pt(13)
        hs.paragraph_format.space_before = Pt(12)

def add_table(headers, rows):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Light Grid Accent 1"
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(10)
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = table.rows[ri + 1].cells[ci]
            cell.text = val
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(10)
    doc.add_paragraph()

def add_quote(text):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.5)
    run = p.add_run(f'"{text}"')
    run.italic = True
    run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    run.font.size = Pt(11)

# ─── TITLE PAGE ───
doc.add_paragraph("\n\n\n")
title = doc.add_heading("Neutramart", level=1)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
for run in title.runs:
    run.font.size = Pt(40)
    run.font.color.rgb = RGBColor(0x1A, 0x56, 0x7E)

subtitle = doc.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = subtitle.add_run("Business Requirements Document")
run.font.size = Pt(18)
run.font.color.rgb = RGBColor(0x66, 0x66, 0x66)

doc.add_paragraph()
version = doc.add_paragraph()
version.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = version.add_run("Version 1.0  |  March 2026")
run.font.size = Pt(12)
run.font.color.rgb = RGBColor(0x99, 0x99, 0x99)

doc.add_page_break()

# ─── THE PROBLEM ───
doc.add_heading("The Problem We're Solving", level=1)

doc.add_paragraph(
    "Every day, millions of people stare at their plate and wonder — "
    '"Is this good for me?"'
)
doc.add_paragraph(
    "They want to eat better. They want to lose weight, build muscle, manage diabetes, "
    "or simply make smarter choices. But nutrition tracking is broken. It's tedious, "
    "inaccurate, and feels like homework. People give up within a week."
)

doc.add_heading("The current experience:", level=3)
bullets = [
    "Manually searching through databases of 800,000+ food items",
    "Guessing portion sizes, ingredients, and cooking methods",
    "Spending 5-10 minutes logging a single meal",
    "Getting it wrong anyway",
]
for b in bullets:
    doc.add_paragraph(b, style="List Bullet")

p = doc.add_paragraph()
run = p.add_run("Nobody has time for that. And nobody should have to.")
run.bold = True
run.font.size = Pt(12)

# ─── WHAT NEUTRAMART DOES ───
doc.add_heading("What Neutramart Does", level=1)

tagline = doc.add_paragraph()
tagline.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = tagline.add_run("Snap. Know. Eat better.")
run.bold = True
run.font.size = Pt(20)
run.font.color.rgb = RGBColor(0x1A, 0x56, 0x7E)

doc.add_paragraph()
doc.add_paragraph(
    "Neutramart turns any smartphone camera into an instant nutrition expert. "
    "Take a photo of your food — any food, any cuisine, any portion size — "
    "and get a complete nutritional breakdown in seconds."
)
doc.add_paragraph("No typing. No searching. No guessing.")
p = doc.add_paragraph()
run = p.add_run("One photo. One tap. Complete clarity.")
run.bold = True

# ─── USER JOURNEY ───
doc.add_heading("How It Works — The User Journey", level=1)

doc.add_heading("1. Sign In with Google", level=2)
doc.add_paragraph(
    "One tap. No new passwords to remember. No forms to fill. The user is in."
)

doc.add_heading("2. Snap or Upload", level=2)
doc.add_paragraph(
    "The user takes a photo of their meal or uploads one from their gallery. "
    "They see their food on screen — familiar, appetizing, exactly as it sits in front of them."
)

doc.add_heading('3. Tap "Analyze Food"', level=2)
doc.add_paragraph("One button. That's it.")
doc.add_paragraph(
    "Behind the scenes, something remarkable happens. The image travels to our cloud, "
    "where an advanced AI — the same class of intelligence that powers the world's most "
    "sophisticated language models — looks at the food. It recognizes the dish. "
    "It estimates the portion. It understands the ingredients."
)

doc.add_heading("4. Instant Results", level=2)
doc.add_paragraph("Within seconds, the user sees:")

add_table(
    ["What They Get", "Why It Matters"],
    [
        ["Food Description", "Confirms what the AI sees — builds trust"],
        ["Estimated Weight", "No more guessing portion sizes"],
        ["Calories", "The number everyone wants to know"],
        ["Protein", "Essential for muscle, recovery, satiety"],
        ["Carbohydrates", "Key for energy management and diabetes care"],
        ["Fat", "Important for heart health awareness"],
        ["Fiber", "The overlooked hero of gut health"],
        ["Sugar", "The hidden villain in modern diets"],
        ["Nutritional Summary", "A plain-English snapshot of the meal"],
        ["Personalized Recommendation", "Actionable advice — what to add, reduce, or pair with"],
    ],
)

doc.add_heading("5. Upload Another", level=2)
doc.add_paragraph(
    "Breakfast, lunch, dinner, snacks — the user builds a picture of their day, "
    "one photo at a time."
)

# ─── TARGET AUDIENCE ───
doc.add_page_break()
doc.add_heading("Who Is This For?", level=1)

doc.add_heading("The Health-Conscious Professional", level=2)
add_quote("I know I should eat better, but I don't have time to track everything.")
doc.add_paragraph(
    "They want speed and simplicity. Neutramart gives them answers in seconds, not minutes."
)

doc.add_heading("The Fitness Enthusiast", level=2)
add_quote("I need to hit my macros — 180g protein, 2,500 calories.")
doc.add_paragraph(
    "They live and die by the numbers. Neutramart makes tracking effortless, "
    "so they can focus on performance."
)

doc.add_heading("The Diabetic Patient", level=2)
add_quote("My doctor told me to watch my carbs and sugar.")
doc.add_paragraph(
    "They need reliable carb and sugar estimates at every meal. "
    "Neutramart puts that information one photo away."
)

doc.add_heading("The Curious Eater", level=2)
add_quote("I just want to know what I'm eating.")
doc.add_paragraph(
    "No goals, no targets — just curiosity. Neutramart satisfies that curiosity instantly, "
    "and sometimes curiosity is where change begins."
)

doc.add_heading("The Parent", level=2)
add_quote("Am I feeding my kids well enough?")
doc.add_paragraph(
    "They worry silently. Neutramart gives them clarity and confidence "
    "without turning mealtime into a science experiment."
)

# ─── COMPETITIVE POSITIONING ───
doc.add_heading("What Makes Neutramart Different", level=1)

doc.add_heading("vs. MyFitnessPal, Lose It!, and Traditional Trackers", level=2)
doc.add_paragraph(
    "They require manual input — searching, selecting, adjusting portions. "
    "It takes 3-5 minutes per meal. Most users quit within 7 days. "
    "Neutramart takes 5 seconds."
)

doc.add_heading("vs. Calorie Mama, Foodvisor, and Other Photo-Based Apps", level=2)
doc.add_paragraph(
    "They use older image recognition models trained on fixed food databases. "
    "They struggle with mixed plates, regional cuisines, and unfamiliar dishes. "
    "Neutramart uses frontier AI that understands food the way a human nutritionist would — "
    "contextually, visually, intelligently."
)

doc.add_heading("vs. Consulting a Nutritionist", level=2)
doc.add_paragraph(
    "A single session costs $100-300. Availability is limited. Feedback is delayed. "
    "Neutramart provides nutritionist-grade insight instantly, at a fraction of the cost, "
    "available 24/7."
)

# ─── BUSINESS MODEL ───
doc.add_page_break()
doc.add_heading("The Business Model", level=1)

doc.add_heading("Phase 1 — Free Tier (Current)", level=2)
for item in [
    "Unlimited photo analyses",
    "Build the user base",
    "Collect anonymized data to improve accuracy",
    "Establish brand trust",
]:
    doc.add_paragraph(item, style="List Bullet")

doc.add_heading("Phase 2 — Premium (Future)", level=2)
for item in [
    "Meal history and daily/weekly tracking — see patterns over time",
    "Goal setting — weight loss, muscle gain, sugar reduction",
    'Meal planning suggestions — "Based on your lunch, here\'s what dinner should look like"',
    "Export reports — share with doctors, trainers, nutritionists",
    "Family accounts — track for the whole household",
]:
    doc.add_paragraph(item, style="List Bullet")

doc.add_heading("Phase 3 — Platform (Future)", level=2)
for item in [
    "API for third parties — gyms, hospitals, wellness apps can embed Neutramart's analysis",
    "Enterprise wellness programs — companies offer Neutramart to employees as a health benefit",
    "Insurance partnerships — healthier eating = lower claims = everyone wins",
]:
    doc.add_paragraph(item, style="List Bullet")

# ─── MARKET OPPORTUNITY ───
doc.add_heading("Market Opportunity", level=1)

add_table(
    ["Metric", "Value"],
    [
        ["Global health & wellness food market", "$1.1 trillion by 2027"],
        ["Calorie counting app users worldwide", "100+ million"],
        ["Average user churn on existing apps (30-day)", "75-80%"],
        ["Users who quit due to \"too much effort\"", "60%+"],
    ],
)

doc.add_paragraph(
    "The market is enormous. The pain is real. And the current solutions are losing users "
    "because they ask too much. Neutramart asks for one thing — a photo."
)

# ─── SUCCESS METRICS ───
doc.add_heading("Key Success Metrics", level=1)

add_table(
    ["Metric", "Target", "Why It Matters"],
    [
        ["Time to first analysis", "Under 30 seconds from sign-in", "Speed is the product"],
        ["Analysis accuracy", "Within 15% of actual values", "Trust drives retention"],
        ["7-day retention", "40%+", "Proves habit formation"],
        ["30-day retention", "25%+", "Proves lasting value"],
        ["Analyses per user per day", "2+", "Shows integration into daily life"],
        ["User satisfaction (NPS)", "50+", "Measures delight, not just usage"],
    ],
)

# ─── SECURITY ───
doc.add_heading("Security & Privacy", level=1)

for item in [
    "Google Sign-In only — no passwords stored, no credentials to leak",
    "Every API request is authenticated — verified against Google's servers",
    "Images are stored securely in encrypted cloud storage",
    "No data is sold — ever",
    "Users own their data — delete your account, we delete everything",
]:
    doc.add_paragraph(item, style="List Bullet")

p = doc.add_paragraph()
run = p.add_run("Trust isn't a feature. It's the foundation.")
run.bold = True
run.italic = True
run.font.size = Pt(12)

# ─── WHAT WE'VE BUILT ───
doc.add_heading("What We've Built So Far", level=1)

doc.add_heading("A fully functional MVP:", level=3)
for item in [
    "Secure Google authentication",
    "Drag-and-drop image upload with real-time progress tracking",
    "AI-powered food analysis returning 10 nutritional data points",
    "Clean, responsive interface that works on any device",
    "Authenticated API with token validation",
    "Cloud-native architecture ready to scale",
]:
    doc.add_paragraph(item, style="List Bullet")

doc.add_heading("What's ready for production:", level=3)
for item in [
    "Backend containerized and deployment-ready for cloud infrastructure",
    "Scalable to thousands of concurrent users",
    "Cost-efficient — pay only for what we use",
]:
    doc.add_paragraph(item, style="List Bullet")

# ─── VISION ───
doc.add_page_break()
doc.add_heading("The Vision", level=1)

doc.add_paragraph(
    "Neutramart isn't just an app. It's a shift in how people relate to food."
)
doc.add_paragraph(
    "Today, we analyze a photo. Tomorrow, we track a day. "
    "Next month, we understand a pattern. Next year, we prevent a disease."
)
doc.add_paragraph(
    'The journey from "What\'s in my food?" to "I\'m healthier because of what I know" '
    "starts with a single photo."
)

p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = p.add_run("Neutramart makes that first step effortless.")
run.bold = True
run.font.size = Pt(16)
run.font.color.rgb = RGBColor(0x1A, 0x56, 0x7E)

# ─── SAVE ───
output_path = "/Users/motududu/Desktop/RIJ/Neutramart_BRD.docx"
doc.save(output_path)
print(f"Saved to {output_path}")
