import Foundation
import Speech
import AVFoundation

// Speech to text with macOS's own on-device engine (SpeechTranscriber, macOS 26). No network, no key.
// usage: transcribe run <audio file> <locale> [<locale> ...]  -> JSON [{locale, text, confidence}] or {error}
//        transcribe status                                    -> JSON {installed: [...], supported: [...]}
//        transcribe install <locale>                          -> downloads Apple's model for a language (the owner runs this once by hand)
// The audio is read, never written. Locales use Apple's names: en_US, zh_CN.

func emit(_ obj: Any) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: obj, options: [])
    print(String(data: data, encoding: .utf8)!)
    exit(0)
}

@available(macOS 26.0, *)
func transcribe(_ path: String, _ id: String) async throws -> [String: Any] {
    let t = SpeechTranscriber(locale: Locale(identifier: id), transcriptionOptions: [], reportingOptions: [],
                              attributeOptions: [.transcriptionConfidence])
    let a = SpeechAnalyzer(modules: [t])
    let file = try AVAudioFile(forReading: URL(fileURLWithPath: path))
    async let collected: (String, Double, Int) = {
        var s = "", sum = 0.0, n = 0
        for try await r in t.results {
            s += String(r.text.characters)
            for run in r.text.runs {
                if let c = run.transcriptionConfidence {
                    let len = r.text[run.range].characters.count
                    sum += c * Double(len)
                    n += len
                }
            }
        }
        return (s, sum, n)
    }()
    try await a.analyzeSequence(from: file)
    try await a.finalizeAndFinishThroughEndOfInput()
    let (text, sum, n) = try await collected
    return ["locale": id, "text": text.trimmingCharacters(in: .whitespacesAndNewlines), "confidence": n > 0 ? sum / Double(n) : 0.0]
}

let args = CommandLine.arguments
guard #available(macOS 26.0, *) else { emit(["error": "needs macOS 26 or later"]) }
let sem = DispatchSemaphore(value: 0)
Task {
    guard #available(macOS 26.0, *) else { return }
    do {
        switch args.count > 1 ? args[1] : "" {
        case "status":
            let inst = await SpeechTranscriber.installedLocales.map { $0.identifier }.sorted()
            let sup = await SpeechTranscriber.supportedLocales.map { $0.identifier }.sorted()
            emit(["installed": inst, "supported": sup])
        case "install" where args.count > 2:
            let t = SpeechTranscriber(locale: Locale(identifier: args[2]), transcriptionOptions: [], reportingOptions: [], attributeOptions: [])
            if let req = try await AssetInventory.assetInstallationRequest(supporting: [t]) { try await req.downloadAndInstall() }
            emit(["installed": args[2]])
        case "run" where args.count > 3:
            var out: [[String: Any]] = []
            for id in args[3...] {
                do { out.append(try await transcribe(args[2], id)) }
                catch { out.append(["locale": id, "error": "\(error.localizedDescription)"]) }   // one language failing (not installed) does not hide the others
            }
            emit(out)
        default:
            emit(["error": "usage: transcribe run <audio> <locale>... | status | install <locale>"])
        }
    } catch { emit(["error": "\(error.localizedDescription)"]) }
}
sem.wait()
