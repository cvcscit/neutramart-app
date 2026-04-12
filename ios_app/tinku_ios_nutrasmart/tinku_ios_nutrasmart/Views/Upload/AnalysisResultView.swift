import SwiftUI

struct AnalysisResultView: View {
    let analysis: SingleAnalysis
    let onNewAnalysis: () -> Void

    var body: some View {
        VStack(spacing: 16) {
            Button { onNewAnalysis() } label: { Label("New Analysis", systemImage: "arrow.left").font(.subheadline) }
                .frame(maxWidth: .infinity, alignment: .leading)

            if let d = analysis.imageData, let img = UIImage(data: d) {
                Image(uiImage: img).resizable().scaledToFill().frame(maxHeight: 200).clipShape(RoundedRectangle(cornerRadius: 12))
            }

            if !analysis.description.isEmpty { Text(analysis.description).font(.subheadline).foregroundStyle(.secondary) }

            NutritionCard(nutrition: analysis.totalNutrition)
            if !analysis.micronutrients.isEmpty { MicronutrientsCard(micronutrients: analysis.micronutrients) }
            if !analysis.dishes.isEmpty { DishesSection(dishes: analysis.dishes) }
            if !analysis.objects.isEmpty { IngredientsCard(objects: analysis.objects) }
            if let r = analysis.recommendation, !r.isEmpty { RecommendationCard(text: r) }
            if analysis.totalNutrition.calories > 0 { ActivitySuggestionsCard(calories: analysis.totalNutrition.calories) }
        }
    }
}

// MARK: - Nutrition Card
struct NutritionCard: View {
    let nutrition: TotalNutrition
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Total Nutrition").font(.subheadline).fontWeight(.semibold).foregroundStyle(.green)
            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 3), spacing: 12) {
                MacroItem(value: "\(Int(nutrition.calories))", label: "Calories", color: .green, large: true)
                MacroItem(value: fmtG(nutrition.protein), label: "Protein", color: .blue)
                MacroItem(value: fmtG(nutrition.carbs), label: "Carbs", color: .orange)
                MacroItem(value: fmtG(nutrition.fat), label: "Fat", color: .yellow)
                MacroItem(value: fmtG(nutrition.fiber), label: "Fiber", color: .purple)
                MacroItem(value: fmtG(nutrition.sugar), label: "Sugar", color: .red)
            }
        }
        .padding()
        .background(LinearGradient(colors: [.green.opacity(0.08), .blue.opacity(0.08)], startPoint: .leading, endPoint: .trailing))
        .cornerRadius(12).overlay(RoundedRectangle(cornerRadius: 12).stroke(.green.opacity(0.3)))
    }
}

struct MacroItem: View {
    let value: String; let label: String; let color: Color; var large: Bool = false
    var body: some View {
        VStack(spacing: 2) {
            Text(value).font(large ? .title2 : .headline).fontWeight(.bold).foregroundStyle(color)
            Text(label).font(.caption2).foregroundStyle(color.opacity(0.8))
        }
    }
}

// MARK: - Micronutrients
struct MicronutrientsCard: View {
    let micronutrients: [String: String]
    private let items: [(key: String, label: String, color: Color)] = [
        ("vitamin_a", "Vit A", .orange), ("vitamin_c", "Vit C", .yellow), ("vitamin_d", "Vit D", .brown),
        ("vitamin_b12", "Vit B12", .pink), ("iron", "Iron", .red), ("calcium", "Calcium", .blue),
        ("potassium", "Potassium", .green), ("sodium", "Sodium", .gray), ("zinc", "Zinc", .teal), ("magnesium", "Magnesium", .indigo),
    ]
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Micronutrients").font(.subheadline).fontWeight(.semibold).foregroundStyle(.purple)
            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 5), spacing: 8) {
                ForEach(items, id: \.key) { item in
                    if let v = micronutrients[item.key], v != "N/A", !v.isEmpty {
                        VStack(spacing: 2) {
                            Text(v).font(.caption2).fontWeight(.semibold).foregroundStyle(item.color)
                            Text(item.label).font(.caption2).foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .padding()
        .background(LinearGradient(colors: [.purple.opacity(0.08), .pink.opacity(0.08)], startPoint: .leading, endPoint: .trailing))
        .cornerRadius(12).overlay(RoundedRectangle(cornerRadius: 12).stroke(.purple.opacity(0.3)))
    }
}

// MARK: - Dishes
struct DishesSection: View {
    let dishes: [Dish]
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Dishes in This Image").font(.subheadline).fontWeight(.semibold)
            ForEach(dishes) { dish in
                VStack(spacing: 8) {
                    HStack {
                        Text(dish.name).font(.subheadline).fontWeight(.semibold)
                        Spacer()
                        Text(dish.servingSize).font(.caption).padding(.horizontal, 8).padding(.vertical, 2).background(.secondary.opacity(0.1)).cornerRadius(6)
                    }
                    HStack(spacing: 0) {
                        DishMacro(value: "\(Int(dish.calories))", label: "Calories", color: .green)
                        DishMacro(value: fmtG(dish.protein), label: "Protein", color: .blue)
                        DishMacro(value: fmtG(dish.carbs), label: "Carbs", color: .orange)
                        DishMacro(value: fmtG(dish.fat), label: "Fat", color: .yellow)
                    }
                    if dish.servingWeightGrams > 0 {
                        Text("Serving: \(Int(dish.servingWeightGrams))g").font(.caption2).foregroundStyle(.secondary).frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding().background(.background).cornerRadius(10).overlay(RoundedRectangle(cornerRadius: 10).stroke(.secondary.opacity(0.2)))
            }
        }
    }
}

struct DishMacro: View {
    let value: String; let label: String; let color: Color
    var body: some View {
        VStack(spacing: 1) {
            Text(value).font(.callout).fontWeight(.bold).foregroundStyle(color)
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }.frame(maxWidth: .infinity)
    }
}

// MARK: - Ingredients
struct IngredientsCard: View {
    let objects: [String]
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Ingredients Identified").font(.subheadline).fontWeight(.semibold).foregroundStyle(.blue)
            FlowLayout(spacing: 6) {
                ForEach(objects, id: \.self) { obj in
                    Text(obj).font(.caption).padding(.horizontal, 10).padding(.vertical, 4).background(.blue.opacity(0.1)).cornerRadius(6)
                }
            }
        }
        .padding().background(.blue.opacity(0.05)).cornerRadius(12).overlay(RoundedRectangle(cornerRadius: 12).stroke(.blue.opacity(0.2)))
    }
}

// MARK: - Recommendation
struct RecommendationCard: View {
    let text: String
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Recommendation", systemImage: "lightbulb").font(.subheadline).fontWeight(.semibold).foregroundStyle(.green)
            Text(text).font(.subheadline).foregroundStyle(.primary.opacity(0.9))
        }
        .padding().background(.green.opacity(0.05)).cornerRadius(12).overlay(RoundedRectangle(cornerRadius: 12).stroke(.green.opacity(0.2)))
    }
}

// MARK: - Activity Suggestions
struct ActivitySuggestionsCard: View {
    let calories: Double
    private let activities: [(name: String, icon: String, cpm: Double)] = [
        ("Running", "figure.run", 10), ("Cycling", "figure.outdoor.cycle", 8),
        ("Walking", "figure.walk", 6), ("Swimming", "figure.pool.swim", 11),
    ]
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Activity Suggestions").font(.subheadline).fontWeight(.semibold).foregroundStyle(.orange)
            Text("Time to burn \(Int(calories)) calories").font(.caption).foregroundStyle(.secondary)
            HStack(spacing: 0) {
                ForEach(activities, id: \.name) { a in
                    VStack(spacing: 4) {
                        Image(systemName: a.icon).font(.title2).foregroundStyle(.orange)
                        Text("\(Int(calories / a.cpm)) min").font(.callout).fontWeight(.bold).foregroundStyle(.orange)
                        Text(a.name).font(.caption2).foregroundStyle(.secondary)
                    }.frame(maxWidth: .infinity)
                }
            }
        }
        .padding()
        .background(LinearGradient(colors: [.orange.opacity(0.08), .yellow.opacity(0.08)], startPoint: .leading, endPoint: .trailing))
        .cornerRadius(12).overlay(RoundedRectangle(cornerRadius: 12).stroke(.orange.opacity(0.3)))
    }
}

// MARK: - Flow Layout
struct FlowLayout: Layout {
    var spacing: CGFloat = 6
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize { arrange(proposal: proposal, subviews: subviews).size }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let r = arrange(proposal: proposal, subviews: subviews)
        for (i, sv) in subviews.enumerated() { guard i < r.pos.count else { break }; sv.place(at: CGPoint(x: bounds.minX + r.pos[i].x, y: bounds.minY + r.pos[i].y), proposal: .unspecified) }
    }
    private func arrange(proposal: ProposedViewSize, subviews: Subviews) -> (pos: [CGPoint], size: CGSize) {
        let mw = proposal.width ?? .infinity; var pos: [CGPoint] = []; var x: CGFloat = 0, y: CGFloat = 0, rh: CGFloat = 0, mh: CGFloat = 0
        for sv in subviews { let s = sv.sizeThatFits(.unspecified); if x + s.width > mw && x > 0 { x = 0; y += rh + spacing; rh = 0 }; pos.append(CGPoint(x: x, y: y)); rh = max(rh, s.height); x += s.width + spacing; mh = max(mh, y + rh) }
        return (pos, CGSize(width: mw, height: mh))
    }
}
