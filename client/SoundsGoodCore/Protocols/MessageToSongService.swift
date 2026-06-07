//
//  MessageToSongService.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import Foundation
import SoundsGoodCore

public protocol MessageToSongService {
    func generateSong(message: String, genre: String) async throws -> RemoteMessage
}
