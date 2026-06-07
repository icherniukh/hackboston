//
//  RemoteMessage.swift
//  SoundsGoodCore
//
//  Created by Yevhen Dubinin on 6/7/26.
//

import Foundation

public struct RemoteMessage: Decodable {
    public let inputMessage: String
    public let lyrics: String
    public let mood: String?
    public let genre: String?
    public let resultURL: String
    public let stylePrompt: String

    enum CodingKeys: String, CodingKey {
        case inputMessage = "input_message"
        case lyrics
        case mood
        case genre
        case resultURL = "result_url"
        case stylePrompt = "style_prompt"
    }
}
