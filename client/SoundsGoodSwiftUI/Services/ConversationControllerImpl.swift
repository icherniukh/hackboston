//
//  ConversationControllerImpl.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import Foundation
import SoundsGoodCore

@Observable
final class ConversationControllerImpl: ConversationController {
    var messageControllers: [any MessageController] = []

    func send(text: String, genre: String, lyricsModel: String?, musicModel: String?) {
        let controller = MessageControllerImpl(
            message: text,
            genre: genre,
            lyricsModel: lyricsModel,
            musicModel: musicModel,
            source: MessageSource.me,
            songService: MessageToSongServiceImpl(),
            downloadService: SongDownloadServiceImpl()
        )
        messageControllers.append(controller)
    }
}
