import SwiftUI
import PhotosUI

struct UploadView: View {
    @EnvironmentObject var authManager: AuthManager
    @StateObject private var manager = ImageAnalysisManager()
    @State private var showPhotoPicker = false
    @State private var showCamera = false
    @State private var photoSelection: [PhotosPickerItem] = []

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    HStack(spacing: 0) {
                        Text("Nutra").font(.system(size: 36, weight: .medium))
                        Text("Smart").font(.system(size: 36, weight: .medium)).foregroundColor(.green)
                    }.padding(.top, 8)

                    if manager.analysis != nil {
                        AnalysisResultView(analysis: manager.analysis!, onNewAnalysis: { manager.reset() })
                    } else {
                        uploadCard
                    }
                }.padding()
            }
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    private var uploadCard: some View {
        VStack(spacing: 20) {
            if !manager.selectedImages.isEmpty {
                imageGrid
                if manager.isLoading {
                    ProgressView(value: manager.progress).tint(.green)
                    Text(statusText).font(.caption).foregroundStyle(.secondary)
                }
            } else {
                Button { showPhotoPicker = true } label: {
                    VStack(spacing: 12) {
                        Image(systemName: "arrow.up.circle").font(.system(size: 32)).foregroundStyle(.secondary)
                        Text("Tap to select food images").font(.subheadline).fontWeight(.medium)
                        Text("Up to 5 images, 4 MB each").font(.caption).foregroundStyle(.tertiary)
                    }
                    .frame(maxWidth: .infinity).padding(40)
                    .background(RoundedRectangle(cornerRadius: 12).strokeBorder(style: StrokeStyle(lineWidth: 2, dash: [8])).foregroundStyle(.secondary.opacity(0.3)))
                }
            }

            Button { showCamera = true } label: {
                Label("Take Photo", systemImage: "camera").frame(maxWidth: .infinity).padding().background(.ultraThinMaterial).cornerRadius(12)
            }.disabled(manager.isLoading || !manager.canAddMore)

            if case .error(let msg) = manager.status {
                Text(msg).font(.caption).foregroundStyle(.red).padding().frame(maxWidth: .infinity).background(.red.opacity(0.1)).cornerRadius(8)
            }

            if !manager.selectedImages.isEmpty && manager.status != .success {
                Button {
                    Task {
                        guard let t = authManager.token, let e = authManager.user?.email else { return }
                        await manager.upload(token: t, email: e)
                    }
                } label: {
                    HStack {
                        if manager.isLoading { ProgressView().tint(.white); Text(statusText) }
                        else { Image(systemName: "eye"); Text("Analyze \(manager.selectedImages.count > 1 ? "\(manager.selectedImages.count) Images" : "Image")") }
                    }.font(.headline).frame(maxWidth: .infinity).padding().background(.green).foregroundStyle(.white).cornerRadius(12)
                }.disabled(manager.isLoading)
            }
        }
        .padding().background(.background).cornerRadius(16).shadow(color: .black.opacity(0.05), radius: 8)
        .photosPicker(isPresented: $showPhotoPicker, selection: $photoSelection, maxSelectionCount: manager.maxImages - manager.selectedImages.count, matching: .images)
        .onChange(of: photoSelection) { _, items in
            Task { for item in items { if let d = try? await item.loadTransferable(type: Data.self), let img = UIImage(data: d) { manager.addImage(img) } }; photoSelection = [] }
        }
        .fullScreenCover(isPresented: $showCamera) { CameraView { manager.addImage($0) } }
    }

    private var imageGrid: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(Array(manager.selectedImages.enumerated()), id: \.offset) { i, img in
                    ZStack(alignment: .topTrailing) {
                        Image(uiImage: img).resizable().scaledToFill().frame(width: 72, height: 72).clipShape(RoundedRectangle(cornerRadius: 8))
                        if !manager.isLoading {
                            Button { manager.removeImage(at: i) } label: {
                                Image(systemName: "xmark.circle.fill").font(.system(size: 18)).foregroundStyle(.white, .black.opacity(0.6))
                            }.offset(x: 4, y: -4)
                        }
                    }
                }
                if manager.canAddMore {
                    Button { showPhotoPicker = true } label: {
                        VStack(spacing: 4) { Image(systemName: "plus").font(.title3); Text("Add").font(.caption2) }
                            .foregroundStyle(.secondary).frame(width: 72, height: 72)
                            .background(RoundedRectangle(cornerRadius: 8).strokeBorder(style: StrokeStyle(lineWidth: 2, dash: [6])).foregroundStyle(.secondary.opacity(0.3)))
                    }
                }
            }
        }
    }

    private var statusText: String {
        switch manager.status {
        case .uploading: return "Uploading... \(Int(manager.progress * 100))%"
        case .analyzing: return "Analyzing food images..."
        default: return ""
        }
    }
}
