//
//  LoadingView.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import SwiftUI

struct LoadingView: View {

    var body: some View {
        if #available(iOS 26, *) {
            Button(action: {}) {
                content
            }
            .tint(Theme.playColor)
            .buttonStyle(.glassProminent)
            .disabled(true)
        } else {
            Button(action: {}) {
                content
            }
            .tint(Theme.playColor)
            .buttonStyle(.borderedProminent)
            .disabled(true)
        }
    }

    private var content: some View {
        HStack {
            ProgressView()
                .imageScale(.large)
            Text("Composing...")
        }
        .padding()
    }
}

#Preview {
    LoadingView()
}
