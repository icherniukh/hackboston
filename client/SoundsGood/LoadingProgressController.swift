//
//  LoadingProgressController.swift
//  SoundsGood
//

import Foundation

protocol LoadingProgressController: AnyObject {
    var currentText: String { get }
    func start(onUpdate: @escaping (String) -> Void)
    func stop()
}

final class LoadingProgressControllerImpl: LoadingProgressController {
    private let steps: [String] = [
        "Idealizing", "Lyricing", "Rhyming", "Writing", "Instrumenting",
        "Playing", "Recording", "Mixing", "Effecting", "Mastering",
        "Rendering", "Producing", "Distributing", "Sending"
    ]

    private(set) var currentText: String = ""
    private var currentIndex: Int = 0
    private var timer: Timer?

    func start(onUpdate: @escaping (String) -> Void) {
        stop()
        currentIndex = 0
        currentText = steps[0] + "..."
        onUpdate(currentText)

        timer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in
            guard let self else { return }
            let nextIndex = self.currentIndex + 1
            guard nextIndex < self.steps.count else { return }
            self.currentIndex = nextIndex
            self.currentText = self.steps[nextIndex] + "..."
            onUpdate(self.currentText)
            if nextIndex == self.steps.count - 1 {
                self.timer?.invalidate()
                self.timer = nil
            }
        }
    }

    func stop() {
        timer?.invalidate()
        timer = nil
    }
}
