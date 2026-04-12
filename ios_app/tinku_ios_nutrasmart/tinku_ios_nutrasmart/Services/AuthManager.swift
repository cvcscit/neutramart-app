import Foundation
import SwiftUI

@MainActor
class AuthManager: ObservableObject {
    @Published var user: AppUser?
    @Published var token: String?
    @Published var isAuthenticated = false

    private let tokenKey = "auth_token"
    private let userKey = "auth_user"

    init() { loadSavedSession() }

    func login(token: String, user: AppUser) {
        self.token = token
        self.user = user
        self.isAuthenticated = true
        UserDefaults.standard.set(token, forKey: tokenKey)
        if let data = try? JSONEncoder().encode(user) {
            UserDefaults.standard.set(data, forKey: userKey)
        }
    }

    func logout() {
        self.token = nil
        self.user = nil
        self.isAuthenticated = false
        UserDefaults.standard.removeObject(forKey: tokenKey)
        UserDefaults.standard.removeObject(forKey: userKey)
    }

    private func loadSavedSession() {
        guard let token = UserDefaults.standard.string(forKey: tokenKey),
              let userData = UserDefaults.standard.data(forKey: userKey),
              let user = try? JSONDecoder().decode(AppUser.self, from: userData) else { return }
        self.token = token
        self.user = user
        self.isAuthenticated = true
    }
}
