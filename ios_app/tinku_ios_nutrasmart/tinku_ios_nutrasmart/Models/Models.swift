import Foundation

// MARK: - User
struct AppUser: Codable {
    let firstName: String
    let email: String
    let picture: String
}

// MARK: - Upload
struct PresignRequest: Codable {
    let filename: String
    let content_type: String
    let email: String
}

struct PresignResponse: Codable {
    let url: String
    let key: String
}

// MARK: - Analysis
struct AnalyzeRequest: Codable {
    let images: [AnalyzeImageItem]
}

struct AnalyzeImageItem: Codable {
    let key: String
    let content_type: String
}

struct AnalysisResponse: Codable {
    let description: String?
    let weight: String?
    let calories: String?
    let protein: String?
    let carbs: String?
    let fat: String?
    let fiber: String?
    let sugar: String?
    let dishes: [DishResponse]?
    let objects: [String]?
    let micronutrients: [String: String]?
    let summary: String?
    let recommendation: String?
}

struct DishResponse: Codable {
    let name: String?
    let servingSize: String?
    let servingWeightGrams: Double?
    let calories: Double?
    let protein: Double?
    let carbs: Double?
    let fat: Double?
    let fiber: Double?
    let sugar: Double?
}

// MARK: - Nutrition
struct TotalNutrition: Codable {
    let calories: Double
    let protein: Double
    let carbs: Double
    let fat: Double
    let fiber: Double
    let sugar: Double
}

struct Dish: Identifiable {
    let id = UUID()
    let name: String
    let servingSize: String
    let servingWeightGrams: Double
    let calories: Double
    let protein: Double
    let carbs: Double
    let fat: Double
}

struct SingleAnalysis: Identifiable {
    let id = UUID()
    let imageData: Data?
    let description: String
    let totalNutrition: TotalNutrition
    let dishes: [Dish]
    let objects: [String]
    let micronutrients: [String: String]
    let recommendation: String?
}

// MARK: - Dashboard
struct NutritionSummary: Codable, Identifiable {
    var id: String { date ?? week_start ?? month_start ?? year_start ?? UUID().uuidString }
    let date: String?
    let week_start: String?
    let month_start: String?
    let year_start: String?
    let total_calories: Double
    let total_protein: Double
    let total_carbs: Double
    let total_fat: Double
    let total_fiber: Double
    let total_sugar: Double?
    let meal_count: Int
    let total_vitamin_a: Double?
    let total_vitamin_c: Double?
    let total_vitamin_d: Double?
    let total_vitamin_b12: Double?
    let total_iron: Double?
    let total_calcium: Double?
    let total_potassium: Double?
    let total_sodium: Double?
    let total_zinc: Double?
    let total_magnesium: Double?
}

struct NutritionSummaryResponse: Codable {
    let data: [NutritionSummary]
}

struct Meal: Codable, Identifiable {
    var id: String { meal_id ?? UUID().uuidString }
    let meal_id: String?
    let meal_name: String?
    let meal_type: String?
    let logged_at: String?
    let total_calories: Double?
    let total_protein: Double?
    let total_carbs: Double?
    let total_fat: Double?
    let description: String?
    let image_url: String?
}

struct MealsResponse: Codable {
    let meals: [Meal]
}

// MARK: - Chat
struct ChatMessage: Identifiable, Codable {
    let id: UUID
    let role: String
    let content: String
    init(role: String, content: String) {
        self.id = UUID()
        self.role = role
        self.content = content
    }
}

struct ChatRequest: Codable {
    let message: String
    let history: [ChatHistoryItem]
}

struct ChatHistoryItem: Codable {
    let role: String
    let content: String
}

struct ChatResponse: Codable {
    let reply: String
}

// MARK: - Weekly Summary
struct WeeklySummaryResponse: Codable {
    let summary: String?
    let message: String?
}

// MARK: - Helpers
func parseNum(_ value: String?) -> Double {
    guard let value = value, value != "N/A" else { return 0 }
    let pattern = try? NSRegularExpression(pattern: "[\\d.]+")
    if let match = pattern?.firstMatch(in: value, range: NSRange(value.startIndex..., in: value)),
       let range = Range(match.range, in: value) {
        return Double(value[range]) ?? 0
    }
    return 0
}

func fmtG(_ val: Double) -> String {
    String(format: "%.1fg", val)
}
