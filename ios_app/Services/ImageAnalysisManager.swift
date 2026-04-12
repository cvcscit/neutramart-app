import Foundation
import UIKit

enum UploadStatus: Equatable {
    case idle, uploading, analyzing, success, error(String)
    static func == (lhs: UploadStatus, rhs: UploadStatus) -> Bool {
        switch (lhs, rhs) {
        case (.idle, .idle), (.uploading, .uploading), (.analyzing, .analyzing), (.success, .success): return true
        case (.error(let a), .error(let b)): return a == b
        default: return false
        }
    }
}

@MainActor
class ImageAnalysisManager: ObservableObject {
    @Published var selectedImages: [UIImage] = []
    @Published var status: UploadStatus = .idle
    @Published var progress: Double = 0
    @Published var analysis: SingleAnalysis?

    let maxImages = 5
    private let api = APIClient.shared

    var canAddMore: Bool { selectedImages.count < maxImages && !isLoading }
    var isLoading: Bool { status == .uploading || status == .analyzing }

    func addImage(_ image: UIImage) {
        guard selectedImages.count < maxImages else { return }
        selectedImages.append(image)
        status = .idle
        analysis = nil
    }

    func removeImage(at index: Int) {
        selectedImages.remove(at: index)
        if selectedImages.isEmpty { reset() }
    }

    func reset() {
        selectedImages = []; status = .idle; progress = 0; analysis = nil
    }

    func upload(token: String, email: String) async {
        guard !selectedImages.isEmpty else { return }
        status = .uploading; progress = 0

        do {
            var items: [AnalyzeImageItem] = []
            for (i, image) in selectedImages.enumerated() {
                guard let data = image.jpegData(compressionQuality: 0.85) else { continue }
                let filename = "photo-\(Int(Date().timeIntervalSince1970))-\(i).jpg"
                let presign = try await api.getPresignedURL(token: token, filename: filename, contentType: "image/jpeg", email: email)
                try await api.uploadToS3(url: presign.url, imageData: data, contentType: "image/jpeg") { [weak self] p in
                    Task { @MainActor in self?.progress = (Double(i) + p) / Double(self?.selectedImages.count ?? 1) }
                }
                items.append(AnalyzeImageItem(key: presign.key, content_type: "image/jpeg"))
            }

            status = .analyzing
            let response = try await api.analyzeFood(token: token, images: items)
            analysis = buildAnalysis(from: response)
            status = .success
            Task { try? await api.generateWeeklySummary(token: token) }
        } catch {
            status = .error(error.localizedDescription)
        }
    }

    private func buildAnalysis(from r: AnalysisResponse) -> SingleAnalysis {
        let tn = TotalNutrition(calories: parseNum(r.calories), protein: parseNum(r.protein), carbs: parseNum(r.carbs), fat: parseNum(r.fat), fiber: parseNum(r.fiber), sugar: parseNum(r.sugar))

        let dishes: [Dish]
        if let raw = r.dishes, !raw.isEmpty {
            dishes = raw.map { Dish(name: $0.name ?? "Unknown", servingSize: $0.servingSize ?? "1 serving", servingWeightGrams: $0.servingWeightGrams ?? 0, calories: $0.calories ?? 0, protein: $0.protein ?? 0, carbs: $0.carbs ?? 0, fat: $0.fat ?? 0) }
        } else {
            dishes = [Dish(name: r.description ?? "Meal", servingSize: r.weight ?? "1 serving", servingWeightGrams: parseNum(r.weight), calories: tn.calories, protein: tn.protein, carbs: tn.carbs, fat: tn.fat)]
        }

        return SingleAnalysis(imageData: selectedImages.first?.jpegData(compressionQuality: 0.5), description: r.description ?? "", totalNutrition: tn, dishes: dishes, objects: r.objects ?? [], micronutrients: r.micronutrients ?? [:], recommendation: r.recommendation)
    }
}
