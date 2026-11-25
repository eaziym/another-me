import Cocoa
import ApplicationServices

// Read-only: the text an app exposes through macOS Accessibility, per window.
// usage: ax_text list            -> running apps
//        ax_text read <app name or bundle id>
// Prints JSON. Never performs actions; skips secure (password) fields.

func get(_ e: AXUIElement, _ n: String) -> AnyObject? {
    var v: AnyObject?
    return AXUIElementCopyAttributeValue(e, n as CFString, &v) == .success ? v : nil
}
func emit(_ obj: Any) -> Never {
    let data = try! JSONSerialization.data(withJSONObject: obj, options: [])
    print(String(data: data, encoding: .utf8)!)
    exit(0)
}

let args = CommandLine.arguments
let regular = NSWorkspace.shared.runningApplications.filter { $0.activationPolicy == .regular }
if args.count < 3 || args[1] == "list" {
    emit(regular.map { ["name": $0.localizedName ?? "", "bundle": $0.bundleIdentifier ?? "", "frontmost": $0.isActive] })
}
if !AXIsProcessTrusted() { emit(["error": "Accessibility permission is not granted to the app running this tool"]) }

let want = args[2].lowercased()
// Some app names carry invisible marks (WhatsApp does), so compare letters and digits only.
func plain(_ s: String) -> String { String(s.lowercased().unicodeScalars.filter { CharacterSet.alphanumerics.contains($0) }) }
guard let app = regular.first(where: { ($0.bundleIdentifier ?? "").lowercased() == want || plain($0.localizedName ?? "") == plain(want) })
    ?? regular.first(where: { plain($0.localizedName ?? "").contains(plain(want)) }) else {
    emit(["error": "no running app matches \(args[2])"])
}
let root = AXUIElementCreateApplication(app.processIdentifier)
AXUIElementSetMessagingTimeout(root, 3)

var nodes = 0
let nodeCap = 20000
func walk(_ e: AXUIElement, _ depth: Int, _ out: inout [String]) {
    nodes += 1
    if depth > 80 || nodes > nodeCap { return }
    let role = (get(e, kAXRoleAttribute) as? String) ?? ""
    let subrole = (get(e, kAXSubroleAttribute) as? String) ?? ""
    if subrole == "AXSecureTextField" { return }
    if role != "AXWindow" && role != "AXApplication" {
        for k in [kAXValueAttribute, kAXTitleAttribute, kAXDescriptionAttribute] {
            if let s = (get(e, k) as? String)?.trimmingCharacters(in: .whitespacesAndNewlines), !s.isEmpty {
                if out.last != s { out.append(s) }
                break
            }
        }
    }
    for child in (get(e, kAXChildrenAttribute) as? [AXUIElement]) ?? [] { walk(child, depth + 1, &out) }
}
func readWindows() -> [[String: Any]] {
    nodes = 0
    var result: [[String: Any]] = []
    for w in (get(root, kAXWindowsAttribute) as? [AXUIElement]) ?? [] {
        var lines: [String] = []
        walk(w, 0, &lines)
        result.append(["title": (get(w, kAXTitleAttribute) as? String) ?? "", "text": lines.joined(separator: "\n")])
    }
    return result
}

var windows = readWindows()
var switched = false
let total = windows.reduce(0) { $0 + (($1["text"] as? String)?.count ?? 0) }
if total < 400 {
    // Electron and Chromium apps (VS Code, Slack, GitHub Desktop) only publish their content on request.
    if AXUIElementSetAttributeValue(root, "AXManualAccessibility" as CFString, kCFBooleanTrue) == .success {
        Thread.sleep(forTimeInterval: 2.5)
        windows = readWindows()
        switched = true
        AXUIElementSetAttributeValue(root, "AXManualAccessibility" as CFString, kCFBooleanFalse)
    }
}
emit([
    "app": app.localizedName ?? "", "bundle": app.bundleIdentifier ?? "",
    "needed_switch_on": switched, "truncated": nodes > nodeCap, "windows": windows,
])
