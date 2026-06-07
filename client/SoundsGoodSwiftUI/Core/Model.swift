//
//  Model.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import Foundation
import SoundsGoodCore

struct Message: Identifiable {
    let id: UUID
    let text: String
    let source: MessageSource

    init(text: String, source: MessageSource) {
        self.id = UUID()
        self.text = text
        self.source = source
    }
}
