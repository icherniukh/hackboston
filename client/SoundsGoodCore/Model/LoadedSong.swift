//
//  LoadedSong.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/7/26.
//

import Foundation

public struct LoadedSong {
    public let remoteMessage: RemoteMessage
    public let localURL: URL

    public init(remoteMessage: RemoteMessage, localURL: URL) {
        self.remoteMessage = remoteMessage
        self.localURL = localURL
    }
}
