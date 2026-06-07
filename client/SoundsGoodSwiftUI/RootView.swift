//
//  RootView.swift
//  SoundsGoodSwiftUI
//
//  Created by Yevhen Dubinin on 6/6/26.
//

import SwiftUI

struct RootView: View {
    var body: some View {
        let vm = ConversationViewModel()
        ConversationView(viewModel: vm)
    }
}

#Preview {
    RootView()
}
