//
//  SongDownloadServiceImpl.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import Foundation

public final class SongDownloadServiceImpl: SongDownloadService {
    public init() {}
    public func download(from url: URL) async throws -> URL {
        let (tempURL, _) = try await URLSession.shared.download(from: url)
        let destination = FileManager.default.temporaryDirectory
            .appendingPathComponent(url.lastPathComponent)
        try? FileManager.default.removeItem(at: destination)
        try FileManager.default.moveItem(at: tempURL, to: destination)
        return destination
    }
}
