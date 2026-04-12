import SwiftUI

@main
struct tinku_ios_nutrasmartApp: App {
    @StateObject private var authManager = AuthManager()

    var body: some Scene {
        WindowGroup {
            if authManager.isAuthenticated {
                MainTabView().environmentObject(authManager)
            } else {
                LoginView().environmentObject(authManager)
            }
        }
    }
}
