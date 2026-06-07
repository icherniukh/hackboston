//
//  PlaybackControllerImpl.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import Foundation
import Observation
import AVFoundation

@Observable
public final class PlaybackControllerImpl: PlaybackController {

    private var audioPlayer: AVAudioPlayer?
    private var audioDelegate = AudioDelegate()

    public private(set) var isPlaying: Bool = false

    public init(url: URL) {
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default)
        try? AVAudioSession.sharedInstance().setActive(true)
        audioPlayer = try? AVAudioPlayer(contentsOf: url)
        audioDelegate.onFinish = { [weak self] in self?.isPlaying = false }
        audioPlayer?.delegate = audioDelegate
        audioPlayer?.prepareToPlay()
    }

    public func togglePlayback() {
        if isPlaying {
            audioPlayer?.stop()
            isPlaying = false
        } else {
            audioPlayer?.play()
            isPlaying = true
        }
    }
}

private final class AudioDelegate: NSObject, AVAudioPlayerDelegate {
    var onFinish: () -> Void = {}
    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        onFinish()
    }
}
