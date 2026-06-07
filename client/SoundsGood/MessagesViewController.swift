//
//  MessagesViewController.swift
//  SoundsGood
//
//  Created by Yevhen Dubinin on 6/7/26.
//

import UIKit
import Messages
import AVFoundation
import SoundsGoodCore

class MessagesViewController: MSMessagesAppViewController {

    private var currentConversation: MSConversation?
    private var loadedSong: LoadedSong?
    private let loadingProgressController: LoadingProgressController = LoadingProgressControllerImpl()
    private let playColor = UIColor(red: 241/255, green: 87/255, blue: 35/255, alpha: 1)
    private let genres = ["pop", "hip-hop", "edm", "metal", "country", "indie pop", "rock", "jazz", "r&b", "classical"]
    private var selectedGenre = "pop"

    // MARK: - Input Bar

    private lazy var genreScrollView: UIScrollView = {
        let sv = UIScrollView()
        sv.showsHorizontalScrollIndicator = false
        sv.translatesAutoresizingMaskIntoConstraints = false
        return sv
    }()

    private lazy var genreStackView: UIStackView = {
        let sv = UIStackView()
        sv.axis = .horizontal
        sv.spacing = 8
        sv.translatesAutoresizingMaskIntoConstraints = false
        return sv
    }()

    private lazy var inputBar: UIVisualEffectView = {
        let bar = UIVisualEffectView(effect: UIBlurEffect(style: .systemMaterial))
        bar.translatesAutoresizingMaskIntoConstraints = false
        return bar
    }()

    private lazy var inputBarDivider: UIView = {
        let divider = UIView()
        divider.backgroundColor = .separator
        divider.translatesAutoresizingMaskIntoConstraints = false
        return divider
    }()

    private lazy var textFieldContainer: UIView = {
        let container = UIView()
        container.backgroundColor = .secondarySystemBackground
        container.layer.cornerRadius = 20
        container.translatesAutoresizingMaskIntoConstraints = false
        return container
    }()

    private lazy var messageTextView: UITextView = {
        let tv = UITextView()
        tv.font = .systemFont(ofSize: 16)
        tv.backgroundColor = .clear
        tv.isScrollEnabled = false
        tv.delegate = self
        tv.translatesAutoresizingMaskIntoConstraints = false
        tv.textContainerInset = .zero
        tv.textContainer.lineFragmentPadding = 0
        return tv
    }()

    private lazy var placeholderLabel: UILabel = {
        let label = UILabel()
        label.text = "Message"
        label.font = .systemFont(ofSize: 16)
        label.textColor = .placeholderText
        label.translatesAutoresizingMaskIntoConstraints = false
        return label
    }()

    private lazy var sendArrowButton: UIButton = {
        var config = UIButton.Configuration.plain()
        config.image = UIImage(systemName: "arrow.up.circle.fill")
        config.preferredSymbolConfigurationForImage = UIImage.SymbolConfiguration(scale: .large)
        let button = UIButton(configuration: config)
        button.tintColor = playColor
        button.isEnabled = false
        button.translatesAutoresizingMaskIntoConstraints = false
        button.setContentCompressionResistancePriority(.required, for: .horizontal)
        button.setContentHuggingPriority(.required, for: .horizontal)
        button.addTarget(self, action: #selector(submitMessage), for: .touchUpInside)
        return button
    }()

    // MARK: - Background

    private lazy var backgroundImageView: UIImageView = {
        let iv = UIImageView(image: UIImage(named: "background"))
        iv.contentMode = .scaleAspectFit
        iv.translatesAutoresizingMaskIntoConstraints = false
        return iv
    }()

    // MARK: - Center Content

    private lazy var loadingIndicator: UIActivityIndicatorView = {
        let indicator = UIActivityIndicatorView(style: .large)
        indicator.color = playColor
        indicator.translatesAutoresizingMaskIntoConstraints = false
        indicator.hidesWhenStopped = true
        return indicator
    }()

    private lazy var loadingLabel: UILabel = {
        let label = UILabel()
        label.textAlignment = .center
        label.font = .systemFont(ofSize: 15, weight: .medium)
        label.textColor = playColor
        label.translatesAutoresizingMaskIntoConstraints = false
        return label
    }()

    private lazy var playbackContainer: UIView = {
        let v = UIView()
        v.translatesAutoresizingMaskIntoConstraints = false
        return v
    }()

    private lazy var sendButton: UIButton = {
        var config = UIButton.Configuration.filled()
        config.title = "Send Song"
        config.cornerStyle = .large
        config.baseBackgroundColor = playColor
        let button = UIButton(configuration: config)
        button.translatesAutoresizingMaskIntoConstraints = false
        button.addTarget(self, action: #selector(sendSong), for: .touchUpInside)
        return button
    }()

    private lazy var cancelButton: UIButton = {
        var config = UIButton.Configuration.plain()
        config.title = "Cancel"
        config.baseForegroundColor = .systemGray
        let button = UIButton(configuration: config)
        button.translatesAutoresizingMaskIntoConstraints = false
        button.addTarget(self, action: #selector(cancelReady), for: .touchUpInside)
        return button
    }()

    // MARK: - Lifecycle

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        setupInputBar()
        setupBackground()
        setupCenterContent()
    }

    private func setupInputBar() {
        view.addSubview(inputBar)
        inputBar.contentView.addSubview(inputBarDivider)
        inputBar.contentView.addSubview(genreScrollView)
        genreScrollView.addSubview(genreStackView)
        inputBar.contentView.addSubview(textFieldContainer)
        textFieldContainer.addSubview(messageTextView)
        textFieldContainer.addSubview(placeholderLabel)
        inputBar.contentView.addSubview(sendArrowButton)

        genres.forEach { genre in
            let button = makeGenrePill(genre)
            genreStackView.addArrangedSubview(button)
        }

        NSLayoutConstraint.activate([
            inputBar.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            inputBar.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            inputBar.bottomAnchor.constraint(equalTo: view.keyboardLayoutGuide.topAnchor),

            inputBarDivider.topAnchor.constraint(equalTo: inputBar.topAnchor),
            inputBarDivider.leadingAnchor.constraint(equalTo: inputBar.leadingAnchor),
            inputBarDivider.trailingAnchor.constraint(equalTo: inputBar.trailingAnchor),
            inputBarDivider.heightAnchor.constraint(equalToConstant: 0.5),

            genreScrollView.topAnchor.constraint(equalTo: inputBarDivider.bottomAnchor),
            genreScrollView.leadingAnchor.constraint(equalTo: inputBar.leadingAnchor),
            genreScrollView.trailingAnchor.constraint(equalTo: inputBar.trailingAnchor),

            genreStackView.topAnchor.constraint(equalTo: genreScrollView.topAnchor, constant: 8),
            genreStackView.bottomAnchor.constraint(equalTo: genreScrollView.bottomAnchor, constant: -8),
            genreStackView.leadingAnchor.constraint(equalTo: genreScrollView.leadingAnchor, constant: 12),
            genreStackView.trailingAnchor.constraint(equalTo: genreScrollView.trailingAnchor, constant: -12),
            genreStackView.heightAnchor.constraint(equalTo: genreScrollView.heightAnchor, constant: -16),

            sendArrowButton.trailingAnchor.constraint(equalTo: inputBar.trailingAnchor, constant: -12),
            sendArrowButton.bottomAnchor.constraint(equalTo: textFieldContainer.bottomAnchor, constant: -4),
            sendArrowButton.widthAnchor.constraint(greaterThanOrEqualToConstant: 44),
            sendArrowButton.heightAnchor.constraint(greaterThanOrEqualToConstant: 44),

            textFieldContainer.topAnchor.constraint(equalTo: genreScrollView.bottomAnchor, constant: 4),
            textFieldContainer.bottomAnchor.constraint(equalTo: inputBar.bottomAnchor, constant: -8),
            textFieldContainer.leadingAnchor.constraint(equalTo: inputBar.leadingAnchor, constant: 12),
            textFieldContainer.trailingAnchor.constraint(equalTo: sendArrowButton.leadingAnchor, constant: -8),

            messageTextView.leadingAnchor.constraint(equalTo: textFieldContainer.leadingAnchor, constant: 12),
            messageTextView.trailingAnchor.constraint(equalTo: textFieldContainer.trailingAnchor, constant: -12),
            messageTextView.topAnchor.constraint(equalTo: textFieldContainer.topAnchor, constant: 10),
            messageTextView.bottomAnchor.constraint(equalTo: textFieldContainer.bottomAnchor, constant: -10),
            messageTextView.heightAnchor.constraint(lessThanOrEqualToConstant: 100),

            placeholderLabel.leadingAnchor.constraint(equalTo: messageTextView.leadingAnchor),
            placeholderLabel.topAnchor.constraint(equalTo: messageTextView.topAnchor),
        ])
    }

    private func makeGenrePill(_ genre: String) -> UIButton {
        let isSelected = genre == selectedGenre
        var config = isSelected ? UIButton.Configuration.filled() : UIButton.Configuration.bordered()
        config.title = genre
        config.cornerStyle = .capsule
        config.baseForegroundColor = isSelected ? .white : playColor
        if isSelected { config.baseBackgroundColor = playColor }
        let button = UIButton(configuration: config)
        button.addTarget(self, action: #selector(genreTapped(_:)), for: .touchUpInside)
        return button
    }

    @objc private func genreTapped(_ sender: UIButton) {
        guard let genre = sender.configuration?.title else { return }
        selectedGenre = genre
        refreshGenrePills()
    }

    private func refreshGenrePills() {
        for (index, view) in genreStackView.arrangedSubviews.enumerated() {
            guard let button = view as? UIButton else { continue }
            let genre = genres[index]
            let isSelected = genre == selectedGenre
            var config = isSelected ? UIButton.Configuration.filled() : UIButton.Configuration.bordered()
            config.title = genre
            config.cornerStyle = .capsule
            config.baseForegroundColor = isSelected ? .white : playColor
            if isSelected { config.baseBackgroundColor = playColor }
            button.configuration = config
        }
    }

    private func setupBackground() {
        view.addSubview(backgroundImageView)
        NSLayoutConstraint.activate([
            backgroundImageView.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 50),
            backgroundImageView.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -50),
            backgroundImageView.bottomAnchor.constraint(equalTo: inputBar.topAnchor),
        ])
    }

    private func setupCenterContent() {
        [loadingIndicator, loadingLabel, playbackContainer, sendButton, cancelButton].forEach { view.addSubview($0) }
        NSLayoutConstraint.activate([
            loadingIndicator.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            loadingIndicator.centerYAnchor.constraint(equalTo: view.centerYAnchor, constant: -20),

            loadingLabel.topAnchor.constraint(equalTo: loadingIndicator.bottomAnchor, constant: 12),
            loadingLabel.centerXAnchor.constraint(equalTo: view.centerXAnchor),

            playbackContainer.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 24),
            playbackContainer.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -24),
            playbackContainer.centerYAnchor.constraint(equalTo: view.centerYAnchor, constant: -40),
            playbackContainer.heightAnchor.constraint(equalToConstant: 60),

            sendButton.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            sendButton.topAnchor.constraint(equalTo: playbackContainer.bottomAnchor, constant: 16),
            sendButton.widthAnchor.constraint(equalToConstant: 200),
            sendButton.heightAnchor.constraint(equalToConstant: 50),

            cancelButton.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            cancelButton.topAnchor.constraint(equalTo: sendButton.bottomAnchor, constant: 4),
        ])
    }

    // MARK: - Conversation Handling

    override func willBecomeActive(with conversation: MSConversation) {
        currentConversation = conversation
        showCompose()
        requestPresentationStyle(.expanded)
    }

    override func didTransition(to presentationStyle: MSMessagesAppPresentationStyle) {
        if presentationStyle == .expanded {
            messageTextView.becomeFirstResponder()
        }
    }

    // MARK: - States

    private func showCompose() {
        backgroundImageView.isHidden = false
        inputBar.isHidden = false
        messageTextView.text = ""
        placeholderLabel.isHidden = false
        sendArrowButton.isEnabled = false
        loadingProgressController.stop()
        loadingIndicator.stopAnimating()
        loadingLabel.isHidden = true
        playbackContainer.isHidden = true
        sendButton.isHidden = true
        cancelButton.isHidden = true
    }

    private func showGenerating() {
        backgroundImageView.isHidden = true
        messageTextView.resignFirstResponder()
        inputBar.isHidden = true
        loadingIndicator.startAnimating()
        loadingLabel.isHidden = false
        playbackContainer.isHidden = true
        sendButton.isHidden = true
        cancelButton.isHidden = true
        loadingProgressController.start { [weak self] text in
            self?.loadingLabel.text = text
        }
    }

    private func showReady() {
        guard let song = loadedSong else { return }
        playbackContainer.subviews.forEach { $0.removeFromSuperview() }
        let playbackView = PlaybackRowView(url: song.localURL, playColor: playColor)
        playbackView.translatesAutoresizingMaskIntoConstraints = false
        playbackContainer.addSubview(playbackView)
        NSLayoutConstraint.activate([
            playbackView.topAnchor.constraint(equalTo: playbackContainer.topAnchor),
            playbackView.bottomAnchor.constraint(equalTo: playbackContainer.bottomAnchor),
            playbackView.leadingAnchor.constraint(equalTo: playbackContainer.leadingAnchor),
            playbackView.trailingAnchor.constraint(equalTo: playbackContainer.trailingAnchor),
        ])
        loadingProgressController.stop()
        loadingIndicator.stopAnimating()
        loadingLabel.isHidden = true
        playbackContainer.isHidden = false
        sendButton.isHidden = false
        cancelButton.isHidden = false
    }

    // MARK: - Generation

    private func generateSong(for message: String) {
        showGenerating()
        let controller: MessageController = MessageControllerImpl(
            message: message,
            genre: selectedGenre,
            source: .me,
            songService: MessageToSongServiceImpl(),
            downloadService: SongDownloadServiceImpl()
        )
        Task { @MainActor in
            do {
                let song = try await controller.send()
                loadedSong = song
                showReady()
            } catch {
                print("Failed to generate song: \(error)")
                showCompose()
            }
        }
    }

    // MARK: - Actions

    @objc private func cancelReady() {
        (playbackContainer.subviews.first as? PlaybackRowView)?.stopPlayback()
        playbackContainer.subviews.forEach { $0.removeFromSuperview() }
        loadedSong = nil
        showCompose()
    }

    @objc private func submitMessage() {
        let text = messageTextView.text.trimmingCharacters(in: .whitespaces)
        guard !text.isEmpty else { return }
        generateSong(for: text)
    }

    @objc private func sendSong() {
        guard let conversation = currentConversation,
              let song = loadedSong else { return }

        Task { @MainActor in
            let (url, filename) = await prepareAttachment(for: song)
            conversation.insertAttachment(url, withAlternateFilename: filename) { [weak self] error in
                if let error = error {
                    print("Failed to insert attachment: \(error)")
                } else {
                    DispatchQueue.main.async {
                        self?.dismiss()
                    }
                }
            }
        }
    }

    // MARK: - Attachment Preparation

    private func prepareAttachment(for song: LoadedSong) async -> (URL, String) {
        let title = song.remoteMessage.inputMessage
        let outputURL = FileManager.default.temporaryDirectory
            .appendingPathComponent(title + ".m4a")
        try? FileManager.default.removeItem(at: outputURL)

        let asset = AVURLAsset(url: song.localURL)
        guard let session = AVAssetExportSession(asset: asset, presetName: AVAssetExportPresetAppleM4A) else {
            return (song.localURL, title)
        }
        session.outputURL = outputURL
        session.outputFileType = .m4a

        let titleItem = AVMutableMetadataItem()
        titleItem.identifier = .commonIdentifierTitle
        titleItem.value = title as NSString

        let common = (try? await asset.load(.commonMetadata)) ?? []
        var metadata = common.filter { $0.identifier != .commonIdentifierTitle }
        metadata.append(titleItem)
        session.metadata = metadata
        await session.export()

        return session.status == .completed ? (outputURL, title) : (song.localURL, title)
    }

    override func didResignActive(with conversation: MSConversation) {}
    override func didReceive(_ message: MSMessage, conversation: MSConversation) {}
    override func didStartSending(_ message: MSMessage, conversation: MSConversation) {}
    override func didCancelSending(_ message: MSMessage, conversation: MSConversation) {}
    override func willTransition(to presentationStyle: MSMessagesAppPresentationStyle) {}
}

// MARK: - UITextViewDelegate

extension MessagesViewController: UITextViewDelegate {
    func textViewDidBeginEditing(_ textView: UITextView) {
        if presentationStyle == .compact {
            requestPresentationStyle(.expanded)
        }
    }

    func textViewDidChange(_ textView: UITextView) {
        placeholderLabel.isHidden = !textView.text.isEmpty
        sendArrowButton.isEnabled = !textView.text.trimmingCharacters(in: .whitespaces).isEmpty
        let fitsHeight = textView.sizeThatFits(CGSize(width: textView.frame.width, height: .infinity)).height
        textView.isScrollEnabled = fitsHeight > 100
    }

    func textView(_ textView: UITextView, shouldChangeTextIn range: NSRange, replacementText text: String) -> Bool {
        if text == "\n" {
            submitMessage()
            return false
        }
        return true
    }
}
