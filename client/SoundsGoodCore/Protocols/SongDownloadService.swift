//
//  SongDownloadService.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import Foundation

public protocol SongDownloadService {
    func download(from url: URL) async throws -> URL
}
