import Foundation
import UIKit

enum APIError: LocalizedError {
    case unauthorized
    case serverError(String)
    case networkError
    case decodingError

    var errorDescription: String? {
        switch self {
        case .unauthorized: return "Please sign in again"
        case .serverError(let msg): return msg
        case .networkError: return "Network error. Check your connection."
        case .decodingError: return "Unexpected response from server"
        }
    }
}

class APIClient {
    static let shared = APIClient()
    private let session = URLSession.shared

    private func request<T: Decodable>(
        path: String,
        method: String = "GET",
        body: (any Encodable)? = nil,
        token: String,
        queryItems: [URLQueryItem]? = nil
    ) async throws -> T {
        var components = URLComponents(string: "\(APIConfig.baseURL)\(path)")!
        components.queryItems = queryItems

        var req = URLRequest(url: components.url!)
        req.httpMethod = method
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        if let body = body {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try JSONEncoder().encode(body)
        }

        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else { throw APIError.networkError }

        if http.statusCode == 401 || http.statusCode == 403 { throw APIError.unauthorized }
        if http.statusCode >= 400 {
            if let err = try? JSONDecoder().decode([String: String].self, from: data), let d = err["detail"] {
                throw APIError.serverError(d)
            }
            throw APIError.serverError("Request failed")
        }

        do { return try JSONDecoder().decode(T.self, from: data) }
        catch { throw APIError.decodingError }
    }

    func getPresignedURL(token: String, filename: String, contentType: String, email: String) async throws -> PresignResponse {
        try await request(path: "/upload/presign", method: "POST", body: PresignRequest(filename: filename, content_type: contentType, email: email), token: token)
    }

    func uploadToS3(url: String, imageData: Data, contentType: String, onProgress: @escaping (Double) -> Void) async throws {
        var req = URLRequest(url: URL(string: url)!)
        req.httpMethod = "PUT"
        req.setValue(contentType, forHTTPHeaderField: "Content-Type")

        let delegate = UploadProgressDelegate(onProgress: onProgress)
        let s = URLSession(configuration: .default, delegate: delegate, delegateQueue: nil)
        let (_, response) = try await s.upload(for: req, from: imageData)

        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw APIError.serverError("Upload to S3 failed")
        }
    }

    func analyzeFood(token: String, images: [AnalyzeImageItem]) async throws -> AnalysisResponse {
        try await request(path: "/analyze", method: "POST", body: AnalyzeRequest(images: images), token: token)
    }

    func getNutritionSummary(token: String, period: String, startDate: String, endDate: String, timezone: String) async throws -> NutritionSummaryResponse {
        try await request(path: "/nutrition/summary", token: token, queryItems: [
            URLQueryItem(name: "period", value: period),
            URLQueryItem(name: "startDate", value: startDate),
            URLQueryItem(name: "endDate", value: endDate),
            URLQueryItem(name: "limit", value: "365"),
            URLQueryItem(name: "timezone", value: timezone),
        ])
    }

    func getMeals(token: String, startDate: String, endDate: String) async throws -> MealsResponse {
        try await request(path: "/meals", token: token, queryItems: [
            URLQueryItem(name: "startDate", value: startDate),
            URLQueryItem(name: "endDate", value: endDate),
            URLQueryItem(name: "limit", value: "100"),
        ])
    }

    func getWeeklySummary(token: String) async throws -> WeeklySummaryResponse {
        try await request(path: "/weekly-summary", token: token)
    }

    func generateWeeklySummary(token: String) async throws {
        let _: [String: String] = try await request(path: "/weekly-summary/generate", method: "POST", token: token)
    }

    func sendChat(token: String, message: String, history: [ChatHistoryItem]) async throws -> ChatResponse {
        try await request(path: "/chat", method: "POST", body: ChatRequest(message: message, history: history), token: token)
    }
}

class UploadProgressDelegate: NSObject, URLSessionTaskDelegate {
    let onProgress: (Double) -> Void
    init(onProgress: @escaping (Double) -> Void) { self.onProgress = onProgress }

    func urlSession(_ session: URLSession, task: URLSessionTask, didSendBodyData bytesSent: Int64, totalBytesSent: Int64, totalBytesExpectedToSend: Int64) {
        DispatchQueue.main.async { self.onProgress(Double(totalBytesSent) / Double(totalBytesExpectedToSend)) }
    }
}
