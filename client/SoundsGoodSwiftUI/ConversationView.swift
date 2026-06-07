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

    func send(text: String, genre: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        controller.send(text: trimmed, genre: genre)
    }
}

struct ConversationView: View {
    @State private var messageText = ""
    @State private var selectedGenre = Genre.all.first!
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

    private func send() {
        viewModel.send(text: messageText, genre: selectedGenre)
        messageText = ""
        isInputFocused = false
    }
}

private enum Genre {
    static let all = ["pop", "hip-hop", "edm", "metal", "country", "indie pop", "rock", "jazz", "r&b", "classical"]
}

#Preview {
    let vm = ConversationViewModel()
    ConversationView(viewModel: vm)
}
