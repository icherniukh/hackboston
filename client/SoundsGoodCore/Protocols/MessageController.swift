//
//  MessageController.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import Foundation
import SoundsGoodCore

public protocol MessageController {
    var id: UUID { get }
    var source: MessageSource { get }
    func send() async throws -> LoadedSong
}
