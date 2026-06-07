//
//  MessageView.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import SwiftUI
import SoundsGoodCore

struct MessageView: View {
    let controller: any MessageController

    @State private var loadedSong: LoadedSong?
    @State private var playbackController: PlaybackControllerImpl?
    @State private var errorMessage: String?

    var body: some View {
        Group {
            if let loadedSong, let playbackController {
                PlaybackView(url: loadedSong.localURL, controller: playbackController)
            } else if let errorMessage {
                ErrorView(message: errorMessage)
            } else {
                LoadingView()
            }
        }
        .task {
            do {
                let result = try await controller.send()
                loadedSong = result
                playbackController = PlaybackControllerImpl(url: result.localURL)
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}

#Preview {
    MessageView(
        controller: MessageControllerImpl(
            message: "houston we don't have any problems",
            genre: "elated and upbeat, just happy",
            source: MessageSource.me,
            songService: MessageToSongServiceImpl(),
            downloadService: SongDownloadServiceImpl()
        )
    )
}
