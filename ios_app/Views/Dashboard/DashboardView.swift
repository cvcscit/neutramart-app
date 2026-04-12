import SwiftUI
import Charts

struct DashboardView: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var period = "daily"
    @State private var summaryData: [NutritionSummary] = []
    @State private var meals: [Meal] = []
    @State private var weeklySummary: String?
    @State private var isLoading = false
    @State private var showWeekly = false
    @State private var startDate = Calendar.current.date(byAdding: .day, value: -7, to: Date())!
    @State private var endDate = Date()

    private let api = APIClient.shared
    private let df: DateFormatter = { let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"; return f }()

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    periodPicker
                    summaryCards
                    if !summaryData.isEmpty { microCard }
                    if let s = weeklySummary { weeklyCard(s) }
                    if !summaryData.isEmpty { calorieChart; macroChart }
                    if !meals.isEmpty { recentMeals }
                }.padding()
            }
            .navigationTitle("Dashboard")
            .task { await fetch() }
            .refreshable { await fetch() }
        }
    }

    private var periodPicker: some View {
        HStack(spacing: 8) {
            ForEach(["daily", "weekly", "monthly"], id: \.self) { p in
                Button { period = p; Task { await fetch() } } label: {
                    Text(p.capitalized).font(.caption).fontWeight(.medium)
                        .padding(.horizontal, 16).padding(.vertical, 8)
                        .background(period == p ? .green : .secondary.opacity(0.1))
                        .foregroundStyle(period == p ? .white : .primary).cornerRadius(8)
                }
            }; Spacer()
        }
    }

    private var summaryCards: some View {
        let s = stats
        return LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            StatCard(title: "Total Calories", value: "\(Int(s.tc))", subtitle: "Avg: \(Int(s.ac))/day", icon: "flame.fill", color: .green)
            StatCard(title: "Meals Logged", value: "\(s.mc)", subtitle: "Over \(s.d) days", icon: "fork.knife", color: .blue)
            StatCard(title: "Protein", value: "\(Int(s.tp))g", subtitle: "Avg: \(Int(s.ap))g/day", icon: "chart.bar.fill", color: .purple)
            StatCard(title: "Days Tracked", value: "\(s.d)", subtitle: "Keep it up!", icon: "calendar", color: .orange)
        }
    }

    private var microCard: some View {
        let items: [(k: String, l: String, u: String, c: Color)] = [
            ("vitamin_a","Vit A","mcg",.orange),("vitamin_c","Vit C","mg",.yellow),("vitamin_d","Vit D","mcg",.brown),
            ("vitamin_b12","Vit B12","mcg",.pink),("iron","Iron","mg",.red),("calcium","Calcium","mg",.blue),
            ("potassium","Potassium","mg",.green),("sodium","Sodium","mg",.gray),("zinc","Zinc","mg",.teal),("magnesium","Magnesium","mg",.indigo),
        ]
        let mt = microTotals
        return VStack(alignment: .leading, spacing: 8) {
            Text("Micronutrient Totals").font(.subheadline).fontWeight(.semibold).foregroundStyle(.purple)
            LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 5), spacing: 8) {
                ForEach(items, id: \.k) { i in
                    let t = mt[i.k] ?? 0; let v = stats.d > 0 && period == "daily" ? Int(t / Double(stats.d)) : Int(t)
                    if v > 0 { VStack(spacing: 2) { Text("\(v) \(i.u)").font(.caption2).fontWeight(.semibold).foregroundStyle(i.c); Text(i.l).font(.caption2).foregroundStyle(.secondary) } }
                }
            }
        }
        .padding()
        .background(LinearGradient(colors: [.purple.opacity(0.08), .pink.opacity(0.08)], startPoint: .leading, endPoint: .trailing))
        .cornerRadius(12).overlay(RoundedRectangle(cornerRadius: 12).stroke(.purple.opacity(0.3)))
    }

    private func weeklyCard(_ s: String) -> some View {
        DisclosureGroup(isExpanded: $showWeekly) { Text(s).font(.caption).padding(.top, 8) } label: {
            Label("7-Day Eating Summary", systemImage: "doc.text").font(.subheadline).fontWeight(.semibold)
        }
        .padding().background(.background).cornerRadius(12).overlay(RoundedRectangle(cornerRadius: 12).stroke(.secondary.opacity(0.2)))
    }

    private var calorieChart: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Daily Calorie Intake").font(.subheadline).fontWeight(.semibold)
            Chart(summaryData) { i in
                let d = i.date ?? i.week_start ?? i.month_start ?? ""
                LineMark(x: .value("Date", d), y: .value("Cal", i.total_calories)).foregroundStyle(.green).interpolationMethod(.catmullRom)
                PointMark(x: .value("Date", d), y: .value("Cal", i.total_calories)).foregroundStyle(.green).symbolSize(30)
            }.frame(height: 200)
        }
        .padding().background(.background).cornerRadius(12).overlay(RoundedRectangle(cornerRadius: 12).stroke(.secondary.opacity(0.2)))
    }

    private var macroChart: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Macronutrient Breakdown").font(.subheadline).fontWeight(.semibold)
            Chart(summaryData) { i in
                let d = i.date ?? i.week_start ?? i.month_start ?? ""
                BarMark(x: .value("Date", d), y: .value("g", i.total_protein)).foregroundStyle(.blue)
                BarMark(x: .value("Date", d), y: .value("g", i.total_carbs)).foregroundStyle(.orange)
                BarMark(x: .value("Date", d), y: .value("g", i.total_fat)).foregroundStyle(.yellow)
            }.frame(height: 200)
        }
        .padding().background(.background).cornerRadius(12).overlay(RoundedRectangle(cornerRadius: 12).stroke(.secondary.opacity(0.2)))
    }

    private var recentMeals: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Recent Meals").font(.subheadline).fontWeight(.semibold)
            ForEach(meals.prefix(5)) { m in
                HStack {
                    VStack(alignment: .leading, spacing: 2) { Text(m.meal_name ?? "Meal").font(.subheadline).fontWeight(.medium); Text(m.meal_type ?? "").font(.caption).foregroundStyle(.secondary) }
                    Spacer()
                    Text("\(Int(m.total_calories ?? 0)) cal").font(.subheadline).fontWeight(.semibold).foregroundStyle(.green)
                }.padding(.vertical, 6); Divider()
            }
        }
        .padding().background(.background).cornerRadius(12).overlay(RoundedRectangle(cornerRadius: 12).stroke(.secondary.opacity(0.2)))
    }

    private func fetch() async {
        guard let t = authManager.token else { return }
        isLoading = true
        let s = df.string(from: startDate), e = df.string(from: endDate), tz = TimeZone.current.identifier
        do {
            async let sr = api.getNutritionSummary(token: t, period: period, startDate: s, endDate: e, timezone: tz)
            async let mr = api.getMeals(token: t, startDate: s, endDate: e)
            async let wr = api.getWeeklySummary(token: t)
            let (a, b, c) = try await (sr, mr, wr)
            summaryData = a.data; meals = b.meals; weeklySummary = c.summary
        } catch {}
        isLoading = false
    }

    private var stats: (tc: Double, tp: Double, mc: Int, d: Int, ac: Double, ap: Double) {
        let tc = summaryData.reduce(0.0) { $0 + $1.total_calories }
        let tp = summaryData.reduce(0.0) { $0 + $1.total_protein }
        let mc = summaryData.reduce(0) { $0 + $1.meal_count }
        let d = summaryData.count
        return (tc, tp, mc, d, d > 0 ? tc / Double(d) : 0, d > 0 ? tp / Double(d) : 0)
    }

    private var microTotals: [String: Double] {
        var t: [String: Double] = [:]
        for i in summaryData {
            t["vitamin_a", default: 0] += i.total_vitamin_a ?? 0; t["vitamin_c", default: 0] += i.total_vitamin_c ?? 0
            t["vitamin_d", default: 0] += i.total_vitamin_d ?? 0; t["vitamin_b12", default: 0] += i.total_vitamin_b12 ?? 0
            t["iron", default: 0] += i.total_iron ?? 0; t["calcium", default: 0] += i.total_calcium ?? 0
            t["potassium", default: 0] += i.total_potassium ?? 0; t["sodium", default: 0] += i.total_sodium ?? 0
            t["zinc", default: 0] += i.total_zinc ?? 0; t["magnesium", default: 0] += i.total_magnesium ?? 0
        }
        return t
    }
}

struct StatCard: View {
    let title: String; let value: String; let subtitle: String; let icon: String; let color: Color
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack { Image(systemName: icon).font(.caption).foregroundStyle(.secondary); Text(title).font(.caption).foregroundStyle(.secondary) }
            Text(value).font(.title2).fontWeight(.bold).foregroundStyle(color)
            Text(subtitle).font(.caption2).foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, alignment: .leading).padding()
        .background(.background).cornerRadius(12).overlay(RoundedRectangle(cornerRadius: 12).stroke(.secondary.opacity(0.15)))
    }
}
