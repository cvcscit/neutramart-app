import SwiftUI

struct LoginView: View {
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        VStack(spacing: 32) {
            Spacer()

            VStack(spacing: 8) {
                (Text("Nutra").font(.system(size: 48, weight: .medium)) +
                 Text("Smart").font(.system(size: 48, weight: .medium)).foregroundColor(.green))

                Text("AI-Powered Nutrition Tracking")
                    .font(.subheadline).foregroundStyle(.secondary)
            }

            Spacer()

            // TODO: Replace with real Google Sign-In SDK
            Button { simulateLogin() } label: {
                HStack(spacing: 12) {
                    Image(systemName: "g.circle.fill").font(.title2)
                    Text("Continue with Google").font(.headline)
                }
                .frame(maxWidth: .infinity).padding()
                .background(.white).foregroundStyle(.black)
                .cornerRadius(12)
                .shadow(color: .black.opacity(0.1), radius: 4, y: 2)
            }
            .padding(.horizontal, 32)

            Text("By signing in, you agree to our Terms of Service")
                .font(.caption2).foregroundStyle(.tertiary)

            Spacer().frame(height: 40)
        }
        .background(LinearGradient(colors: [.green.opacity(0.05), .white], startPoint: .top, endPoint: .bottom).ignoresSafeArea())
    }

    private func simulateLogin() {
        authManager.login(token: "test-token", user: AppUser(firstName: "Test", email: "test@example.com", picture: ""))
    }
}
