//
//  PlaybackController.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import Foundation

public protocol PlaybackController {
    var isPlaying: Bool { get }
    func togglePlayback()
}
