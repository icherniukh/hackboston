//
//  ErrorView.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import SwiftUI

struct ErrorView: View {
    let message: String

    var body: some View {
        if #available(iOS 26, *) {
            Button(action: {}) {
                content
            }
            .tint(Theme.errorColor)
            .buttonStyle(.glassProminent)
            .disabled(false)
        } else {
            Button(action: {}) {
                content
            }
            .tint(Theme.errorColor)
            .buttonStyle(.borderedProminent)
            .disabled(false)
        }
    }

    private var content: some View {
        HStack {
            Text("⚠️")
            Text(message)
                .multilineTextAlignment(.leading)
        }
        .padding()
    }
}

#Preview {
    ErrorView(message: "The given data was not valid JSON.")
}
