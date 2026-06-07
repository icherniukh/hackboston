//
//  WaveformView.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import SwiftUI

struct WaveformView: View {
    let amplitudes: [Float]

    var body: some View {
        Canvas { context, size in
            guard !amplitudes.isEmpty else { return }

            let count = amplitudes.count
            let spacing: CGFloat = 2
            let barWidth = max(1, (size.width - spacing * CGFloat(count - 1)) / CGFloat(count))
            let minHeight = size.height * 0.06

            for (i, amplitude) in amplitudes.enumerated() {
                let barHeight = max(minHeight, size.height * CGFloat(amplitude))
                let x = CGFloat(i) * (barWidth + spacing)
                let y = (size.height - barHeight) / 2
                let rect = CGRect(x: x, y: y, width: barWidth, height: barHeight)
                let path = Path(roundedRect: rect, cornerRadius: barWidth / 2)
                context.fill(path, with: .color(.white.opacity(0.85)))
            }
        }
    }
}

#Preview {
    let amplitudes: [Float] = (0..<55).map { i in
        let t = Float(i) / Float(55)
        return 0.1 + 0.85 * sin(.pi * t) * Float.random(in: 0.5...1.0)
    }
    WaveformView(amplitudes: amplitudes)
        .frame(width: 220, height: 36)
        .background(Color.gray)
}
