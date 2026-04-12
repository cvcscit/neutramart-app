import SwiftUI

struct MainTabView: View {
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        TabView {
            UploadView().tabItem { Label("Scan", systemImage: "camera.fill") }
            DashboardView().tabItem { Label("Dashboard", systemImage: "chart.bar.fill") }
            ChatView().tabItem { Label("Chat", systemImage: "message.fill") }
            ProfileView().tabItem { Label("Profile", systemImage: "person.fill") }
        }
        .tint(.green)
    }
}

struct ProfileView: View {
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        NavigationStack {
            List {
                if let user = authManager.user {
                    Section {
                        HStack(spacing: 12) {
                            AsyncImage(url: URL(string: user.picture)) { image in
                                image.resizable().scaledToFill()
                            } placeholder: {
                                Image(systemName: "person.circle.fill").font(.system(size: 40)).foregroundStyle(.gray)
                            }
                            .frame(width: 50, height: 50).clipShape(Circle())

                            VStack(alignment: .leading) {
                                Text(user.firstName).font(.headline)
                                Text(user.email).font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }
                Section {
                    Button(role: .destructive) { authManager.logout() } label: {
                        Label("Sign Out", systemImage: "rectangle.portrait.and.arrow.right")
                    }
                }
            }
            .navigationTitle("Profile")
        }
    }
}
