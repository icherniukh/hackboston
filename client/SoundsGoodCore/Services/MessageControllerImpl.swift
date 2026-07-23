//
//  MessageControllerImpl.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import Foundation
import SoundsGoodCore

public final class MessageControllerImpl: MessageController {
    public let id = UUID()
    public let source: MessageSource

    private let message: String
    private let genre: String
    private let lyricsModel: String?
    private let musicModel: String?
    private let songService: MessageToSongService
    private let downloadService: SongDownloadService
    private let baseURL = "https://nugget-freeing-grip.ngrok-free.dev"

    public init(message: String, genre: String, lyricsModel: String? = nil, musicModel: String? = nil, source: MessageSource, songService: MessageToSongService, downloadService: SongDownloadService) {
        self.message = message
        self.genre = genre
        self.lyricsModel = lyricsModel
        self.musicModel = musicModel
        self.source = source
        self.songService = songService
        self.downloadService = downloadService
    }

    public func send() async throws -> LoadedSong {
        let remoteMessage = try await songService.generateSong(message: message, genre: genre, lyricsModel: lyricsModel, musicModel: musicModel)

        guard let songURL = URL(string: baseURL + remoteMessage.resultURL) else {
            throw URLError(.badURL)
        }
        let localURL = try await downloadService.download(from: songURL)
        return LoadedSong(remoteMessage: remoteMessage, localURL: localURL)
    }
}
