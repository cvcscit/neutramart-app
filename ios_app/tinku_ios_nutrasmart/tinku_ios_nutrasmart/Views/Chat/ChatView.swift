import SwiftUI

struct ChatView: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var messages: [ChatMessage] = [
        ChatMessage(role: "assistant", content: "Hi! I'm your NutraSmart AI assistant. Ask me anything about your eating habits, nutrition, or diet recommendations.")
    ]
    @State private var inputText = ""
    @State private var isLoading = false
    @FocusState private var focused: Bool

    private let api = APIClient.shared

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(messages) { msg in MessageBubble(message: msg) }
                            if isLoading {
                                HStack(spacing: 4) { ForEach(0..<3, id: \.self) { _ in Circle().fill(.secondary).frame(width: 8, height: 8).opacity(0.6) } }
                                    .frame(maxWidth: .infinity, alignment: .leading).padding(.horizontal).id("typing")
                            }
                        }.padding()
                    }
                    .onChange(of: messages.count) { _, _ in withAnimation { if let lastId = messages.last?.id { proxy.scrollTo(lastId, anchor: .bottom) } } }
                }

                Divider()

                HStack(spacing: 12) {
                    TextField("Ask about your diet...", text: $inputText)
                        .textFieldStyle(.roundedBorder).focused($focused).disabled(isLoading).onSubmit { send() }
                    Button { send() } label: {
                        Image(systemName: "arrow.up.circle.fill").font(.title2).foregroundStyle(canSend ? .green : .gray)
                    }.disabled(!canSend)
                }.padding()
            }
            .navigationTitle("NutraSmart AI").navigationBarTitleDisplayMode(.inline)
        }
    }

    private var canSend: Bool { !inputText.trimmingCharacters(in: .whitespaces).isEmpty && !isLoading }

    private func send() {
        let text = inputText.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty, !isLoading else { return }
        messages.append(ChatMessage(role: "user", content: text)); inputText = ""; isLoading = true

        Task {
            do {
                guard let t = authManager.token else { return }
                let h = messages.filter { $0.role != "system" }.map { ChatHistoryItem(role: $0.role, content: $0.content) }
                let r = try await api.sendChat(token: t, message: text, history: h)
                messages.append(ChatMessage(role: "assistant", content: r.reply))
            } catch { messages.append(ChatMessage(role: "assistant", content: "Sorry, something went wrong. Please try again.")) }
            isLoading = false
        }
    }
}

struct MessageBubble: View {
    let message: ChatMessage
    private var isUser: Bool { message.role == "user" }

    var body: some View {
        HStack {
            if isUser { Spacer(minLength: 60) }
            Text(message.content).font(.subheadline).padding(12)
                .background(isUser ? .green : Color(.systemGray6))
                .foregroundStyle(isUser ? .white : .primary)
                .cornerRadius(16, corners: isUser ? [.topLeft, .topRight, .bottomLeft] : [.topLeft, .topRight, .bottomRight])
            if !isUser { Spacer(minLength: 60) }
        }
    }
}

extension View {
    func cornerRadius(_ radius: CGFloat, corners: UIRectCorner) -> some View {
        clipShape(RoundedCorner(radius: radius, corners: corners))
    }
}

struct RoundedCorner: Shape {
    var radius: CGFloat; var corners: UIRectCorner
    func path(in rect: CGRect) -> Path {
        Path(UIBezierPath(roundedRect: rect, byRoundingCorners: corners, cornerRadii: CGSize(width: radius, height: radius)).cgPath)
    }
}
