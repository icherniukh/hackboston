//
//  MessageToSongServiceImpl.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import Foundation
import SoundsGoodCore

public final class MessageToSongServiceImpl: MessageToSongService {
    private let baseURL = "https://nugget-freeing-grip.ngrok-free.dev"

    public init() {}

    public func generateSong(message: String, genre: String, lyricsModel: String?, musicModel: String?) async throws -> RemoteMessage {
        guard let url = URL(string: "\(baseURL)/generate-song") else {
            throw URLError(.badURL)
        }
        var body: [String: String] = ["input_message": message, "genre": genre]
        if let lyricsModel, !lyricsModel.isEmpty {
            body["lyrics_model"] = lyricsModel
        }
        if let musicModel, !musicModel.isEmpty {
            body["music_model"] = musicModel
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(body)

        let (data, _) = try await URLSession.shared.data(for: request)
        return try JSONDecoder().decode(RemoteMessage.self, from: data)
    }
}
