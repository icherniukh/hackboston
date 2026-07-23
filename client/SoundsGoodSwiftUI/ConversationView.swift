//
//  ConversationView.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import SwiftUI
import SoundsGoodCore

@Observable
final class ConversationViewModel {

    private let controller = ConversationControllerImpl()

    var messageControllers: [any MessageController] {
        controller.messageControllers
    }

    func send(text: String, genre: String, lyricsModel: String?, musicModel: String?) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        controller.send(text: trimmed, genre: genre, lyricsModel: lyricsModel, musicModel: musicModel)
    }
}

struct ConversationView: View {
    @State private var messageText = ""
    @State private var selectedGenre = Genre.all.first!
    @State private var selectedLyricsModel = LyricsModel.all.first!.id
    @State private var selectedMusicModel = MusicModel.defaultId
    @FocusState private var isInputFocused: Bool

    @Bindable var viewModel: ConversationViewModel

    init(viewModel: ConversationViewModel) {
        self.viewModel = viewModel
    }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(viewModel.messageControllers, id: \.id) { messageController in
                        MessageView(controller: messageController)
                            .padding(.horizontal)
                            .id(messageController.id)
                            .frame(maxWidth: .infinity, alignment: messageController.source == .me ? .trailing : .leading)
                    }
                }
                .padding(.vertical, 8)
            }
            .onChange(of: viewModel.messageControllers.count) {
                if let last = viewModel.messageControllers.last {
                    withAnimation {
                        proxy.scrollTo(last.id, anchor: .bottom)
                    }
                }
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            inputBar
        }
    }

    private var inputBar: some View {
        VStack(spacing: 0) {
            modelPickers
            genreScroller
            HStack(alignment: .bottom, spacing: 12) {
                TextField("Message", text: $messageText, axis: .vertical)
                    .lineLimit(1...3)
                    .focused($isInputFocused)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(Color(.secondarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 20))

                Button(action: send) {
                    Image(systemName: "arrow.up.circle.fill")
                        .imageScale(.large)
                        .foregroundStyle(Theme.playColor)
                }
                .disabled(messageText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
        }
        .background(.regularMaterial)
        .overlay(alignment: .top) { Divider() }
    }

    private var genreScroller: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(Genre.all, id: \.self) { genre in
                    genrePill(genre)
                }
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
        }
    }

    @ViewBuilder
    private func genrePill(_ genre: String) -> some View {
        let isSelected = genre == selectedGenre
        if #available(iOS 26, *) {
            if isSelected {
                Button(genre) { selectedGenre = genre }
                    .tint(Theme.playColor)
                    .buttonStyle(.glassProminent)
            } else {
                Button(genre) { selectedGenre = genre }
                    .buttonStyle(.glass)
            }
        } else {
            if isSelected {
                Button(genre) { selectedGenre = genre }
                    .tint(Theme.playColor)
                    .buttonStyle(.borderedProminent)
            } else {
                Button(genre) { selectedGenre = genre }
                    .buttonStyle(.bordered)
            }
        }
    }

    private var modelPickers: some View {
        HStack(spacing: 8) {
            Menu {
                ForEach(LyricsModel.all, id: \.id) { model in
                    Button(model.label) { selectedLyricsModel = model.id }
                }
            } label: {
                modelPickerLabel(title: "Lyrics", value: selectedLyricsModelLabel)
            }

            Menu {
                ForEach(MusicModel.groups, id: \.name) { group in
                    Menu(group.name) {
                        ForEach(group.options, id: \.id) { model in
                            Button(model.label) { selectedMusicModel = model.id }
                        }
                    }
                }
            } label: {
                modelPickerLabel(title: "Music", value: selectedMusicModelLabel)
            }

            Spacer()
        }
        .padding(.horizontal)
        .padding(.top, 8)
    }

    private var selectedLyricsModelLabel: String {
        LyricsModel.all.first(where: { $0.id == selectedLyricsModel })?.label ?? selectedLyricsModel
    }

    private var selectedMusicModelLabel: String {
        for group in MusicModel.groups {
            if let match = group.options.first(where: { $0.id == selectedMusicModel }) {
                return match.label
            }
        }
        return selectedMusicModel
    }

    @ViewBuilder
    private func modelPickerLabel(title: String, value: String) -> some View {
        HStack(spacing: 4) {
            Text("\(title):")
                .foregroundStyle(.secondary)
            Text(value)
                .lineLimit(1)
            Image(systemName: "chevron.up.chevron.down")
                .imageScale(.small)
        }
        .font(.caption)
        .foregroundStyle(.primary)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(Color(.secondarySystemBackground))
        .clipShape(Capsule())
    }

    private func send() {
        viewModel.send(text: messageText, genre: selectedGenre, lyricsModel: selectedLyricsModel, musicModel: selectedMusicModel)
        messageText = ""
        isInputFocused = false
    }
}

private enum Genre {
    static let all = ["pop", "hip-hop", "edm", "metal", "country", "indie pop", "rock", "jazz", "r&b", "classical", "trap", "trap hip hop", "dark minimal techno", "tech house", "drum & bass"]
}

// Keys must match backend/integrations/openrouter.py's model ids.
private enum LyricsModel {
    static let all: [(id: String, label: String)] = [
        ("z-ai/glm-5.2", "GLM 5.2 (default)"),
        ("moonshotai/kimi-k2.6", "Kimi K2.6"),
        ("moonshotai/kimi-k2.7-code", "Kimi K2.7 Code"),
        ("minimax/minimax-m3", "MiniMax M3"),
        ("deepseek/deepseek-v4-pro", "DeepSeek V4 Pro"),
        ("deepseek/deepseek-v4-flash", "DeepSeek V4 Flash"),
        ("x-ai/grok-4.5", "Grok 4.5"),
        ("google/gemma-4-31b-it", "Gemma 4 31B (legacy)"),
    ]
}

// Groups/keys must match backend/integrations/music_provider.py's _PROVIDERS dict.
private enum MusicModel {
    /// Matches backend DEFAULT_PROVIDER when clients always send an explicit id.
    static let defaultId = "suno"
    static let groups: [(name: String, options: [(id: String, label: String)])] = [
        ("fal.ai", [
            ("ace-step", "ACE-Step"),
            ("ace-step-prompt", "ACE-Step (prompt-to-audio)"),
            ("minimax-v2", "MiniMax Music v2"),
            ("minimax-v2.5", "MiniMax Music v2.5"),
            ("minimax-v2.6", "MiniMax Music v2.6"),
            ("lyria3", "Lyria 3"),
            ("elevenlabs", "ElevenLabs Music"),
        ]),
        ("Suno", [("suno", "Suno")]),
        ("Replicate", [
            ("replicate-ace-step-1.5", "ACE-Step 1.5"),
            ("replicate-stable-audio-2.5", "Stable Audio 2.5"),
        ]),
        ("Runware", [
            ("runware", "Runware Default"),
            ("runware:ace-step@v1.5-xl-sft", "ACE-Step v1.5 XL SFT"),
            ("runware:ace-step@v1.5-xl-turbo", "ACE-Step v1.5 XL Turbo"),
            ("runware:ace-step@v1.5-xl-base", "ACE-Step v1.5 XL Base"),
        ]),
    ]
}

#Preview {
    let vm = ConversationViewModel()
    ConversationView(viewModel: vm)
}
