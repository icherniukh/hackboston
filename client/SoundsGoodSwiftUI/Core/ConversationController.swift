//
//  ConversationController.swift
//  SoundsGoodSwiftUI
//

import SoundsGoodCore

protocol ConversationController {
    var messageControllers: [any MessageController] { get }
    func send(text: String, genre: String, lyricsModel: String?, musicModel: String?)
}
