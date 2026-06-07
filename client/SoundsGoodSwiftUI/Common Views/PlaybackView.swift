//
//  PlaybackView.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import SwiftUI
import AVFoundation
import SoundsGoodCore

struct PlaybackView: View {
    @State private var playbackController: PlaybackController
    @State private var amplitudes: [Float] = []

    private let url: URL
    private let barCount = 55

    init(url: URL, controller: PlaybackController) {
        self.url = url
        self._playbackController = State(initialValue: controller)
    }

    var body: some View {
        buttonView
            .task { amplitudes = await loadAmplitudes(from: url, barCount: barCount) }
    }

    @ViewBuilder
    private var buttonView: some View {
        if #available(iOS 26, *) {
            Button(action: playbackController.togglePlayback) {
                buttonContent
            }
            .tint(Theme.playColor)
            .buttonStyle(.glassProminent)
        } else {
            Button(action: playbackController.togglePlayback) {
                buttonContent
            }
            .tint(Theme.playColor)
            .buttonStyle(.borderedProminent)
        }
    }

    private var buttonContent: some View {
        HStack(spacing: 12) {
            Image(systemName: playbackController.isPlaying ? "stop.fill" : "play.fill")
                .imageScale(.large)
                .frame(width: 22, alignment: .center)

            WaveformView(amplitudes: amplitudes.isEmpty ? placeholder : amplitudes)
                .frame(width: 160, height: 36)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    private var placeholder: [Float] {
        Array(repeating: 0.15, count: barCount)
    }
}

private func loadAmplitudes(from url: URL, barCount: Int) async -> [Float] {
    await Task.detached(priority: .userInitiated) {
        guard let file = try? AVAudioFile(forReading: url) else {
            return Array(repeating: 0.3, count: barCount)
        }

        let format = file.processingFormat
        let totalFrames = file.length
        guard totalFrames > 0 else { return Array(repeating: 0.3, count: barCount) }

        let framesPerBar = max(1, totalFrames / Int64(barCount))
        let chunkSize = AVAudioFrameCount(min(framesPerBar, 4096))

        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: chunkSize) else {
            return Array(repeating: 0.3, count: barCount)
        }

        var amplitudes = [Float](repeating: 0, count: barCount)
        for i in 0..<barCount {
            file.framePosition = Int64(i) * framesPerBar
            try? file.read(into: buffer, frameCount: chunkSize)
            guard let data = buffer.floatChannelData?[0], buffer.frameLength > 0 else { continue }
            let len = Int(buffer.frameLength)
            var rms: Float = 0
            for j in 0..<len { rms += data[j] * data[j] }
            amplitudes[i] = sqrt(rms / Float(len))
        }

        let peak = amplitudes.max() ?? 1
        return peak > 0 ? amplitudes.map { $0 / peak } : amplitudes
    }.value
}

#Preview {
    if let url = Bundle.main.url(forResource: "boston-hackattack", withExtension: "mp3") {
        PlaybackView(url: url, controller: PlaybackControllerImpl(url: url))
    }
}
