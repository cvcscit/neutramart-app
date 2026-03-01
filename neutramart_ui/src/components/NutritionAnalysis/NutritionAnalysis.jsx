import "./NutritionAnalysis.css";

const NUTRIENTS = [
  { key: "calories", label: "Calories" },
  { key: "protein", label: "Protein" },
  { key: "carbs", label: "Carbs" },
  { key: "fat", label: "Fat" },
  { key: "fiber", label: "Fiber" },
  { key: "sugar", label: "Sugar" },
];

export default function NutritionAnalysis({ analysis }) {
  return (
    <div className="analysis-panel">
      <div className="analysis-section">
        <h4 className="analysis-section-title">Summary</h4>
        <p className="analysis-section-text">{analysis.summary}</p>
      </div>

      <h3 className="analysis-title">Nutrition Analysis</h3>
      <p className="analysis-description">{analysis.description}</p>

      <div className="nutrition-grid">
        {NUTRIENTS.map(({ key, label }) => (
          <div className="nutrition-item" key={key}>
            <span className="nutrition-value">{analysis[key]}</span>
            <span className="nutrition-label">{label}</span>
          </div>
        ))}
      </div>

      <div className="analysis-section">
        <h4 className="analysis-section-title">Recommendation</h4>
        <p className="analysis-section-text">{analysis.recommendation}</p>
      </div>
    </div>
  );
}
