//
//  PlaybackRowView.swift
//  SoundsGood
//

import UIKit
import AVFoundation
import Observation
import SoundsGoodCore

// MARK: - WaveformBarView

final class WaveformBarView: UIView {
    var amplitudes: [Float] = [] { didSet { setNeedsDisplay() } }

    override var isOpaque: Bool { get { false } set {} }

    override func draw(_ rect: CGRect) {
        guard !amplitudes.isEmpty else { return }
        let count = amplitudes.count
        let spacing: CGFloat = 2
        let barWidth = max(1, (rect.width - spacing * CGFloat(count - 1)) / CGFloat(count))
        let minHeight = rect.height * 0.06

        UIColor.white.withAlphaComponent(0.85).setFill()
        for (i, amplitude) in amplitudes.enumerated() {
            let barHeight = max(minHeight, rect.height * CGFloat(amplitude))
            let x = CGFloat(i) * (barWidth + spacing)
            let y = (rect.height - barHeight) / 2
            let path = UIBezierPath(
                roundedRect: CGRect(x: x, y: y, width: barWidth, height: barHeight),
                cornerRadius: barWidth / 2
            )
            path.fill()
        }
    }
}

// MARK: - PlaybackRowView

final class PlaybackRowView: UIView {
    private let barCount = 55
    private let controller: PlaybackControllerImpl

    private lazy var playButton: UIButton = {
        var config = UIButton.Configuration.plain()
        config.image = UIImage(systemName: "play.fill")
        config.preferredSymbolConfigurationForImage = UIImage.SymbolConfiguration(pointSize: 18, weight: .medium)
        let button = UIButton(configuration: config)
        button.tintColor = .white
        button.translatesAutoresizingMaskIntoConstraints = false
        button.setContentCompressionResistancePriority(.required, for: .horizontal)
        button.setContentHuggingPriority(.required, for: .horizontal)
        button.addTarget(self, action: #selector(togglePlayback), for: .touchUpInside)
        return button
    }()

    private lazy var waveformView: WaveformBarView = {
        let v = WaveformBarView()
        v.translatesAutoresizingMaskIntoConstraints = false
        v.amplitudes = Array(repeating: 0.15, count: barCount)
        return v
    }()

    init(url: URL, playColor: UIColor) {
        controller = PlaybackControllerImpl(url: url)
        super.init(frame: .zero)
        backgroundColor = playColor
        layer.cornerRadius = 20
        clipsToBounds = true
        setupLayout()
        observePlayback()
        Task.detached(priority: .userInitiated) { [weak self, barCount] in
            guard let self else { return }
            let amps = await self.computeAmplitudes(from: url, barCount: barCount)
            await MainActor.run { self.waveformView.amplitudes = amps }
        }
    }

    required init?(coder: NSCoder) { fatalError() }

    private func setupLayout() {
        addSubview(playButton)
        addSubview(waveformView)
        NSLayoutConstraint.activate([
            playButton.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 16),
            playButton.centerYAnchor.constraint(equalTo: centerYAnchor),
            playButton.widthAnchor.constraint(equalToConstant: 22),

            waveformView.leadingAnchor.constraint(equalTo: playButton.trailingAnchor, constant: 12),
            waveformView.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -16),
            waveformView.topAnchor.constraint(equalTo: topAnchor, constant: 14),
            waveformView.bottomAnchor.constraint(equalTo: bottomAnchor, constant: -14),
        ])
    }

    @objc private func togglePlayback() {
        controller.togglePlayback()
    }

    private func observePlayback() {
        withObservationTracking {
            updatePlayButton(isPlaying: controller.isPlaying)
        } onChange: { [weak self] in
            DispatchQueue.main.async { self?.observePlayback() }
        }
    }

    private func updatePlayButton(isPlaying: Bool) {
        var config = playButton.configuration ?? UIButton.Configuration.plain()
        config.image = UIImage(systemName: isPlaying ? "stop.fill" : "play.fill")
        config.preferredSymbolConfigurationForImage = UIImage.SymbolConfiguration(pointSize: 18, weight: .medium)
        playButton.configuration = config
    }

    func stopPlayback() {
        if controller.isPlaying { controller.togglePlayback() }
    }

    private func computeAmplitudes(from url: URL, barCount: Int) async -> [Float] {
        guard let file = try? AVAudioFile(forReading: url) else {
            return Array(repeating: 0.3, count: barCount)
        }
        let totalFrames = file.length
        guard totalFrames > 0 else { return Array(repeating: 0.3, count: barCount) }
        let framesPerBar = max(1, totalFrames / Int64(barCount))
        let chunkSize = AVAudioFrameCount(min(framesPerBar, 4096))
        guard let buffer = AVAudioPCMBuffer(pcmFormat: file.processingFormat, frameCapacity: chunkSize) else {
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
    }
}
