import Foundation
import EventKit

// Minimal arg parsing helpers
struct Argv {
    let args: [String]
    func has(_ key: String) -> Bool { args.contains(key) }
    func value(after key: String) -> String? {
        guard let i = args.firstIndex(of: key), i+1 < args.count else { return nil }
        return args[i+1]
    }
}

@inline(__always) func readEnv(_ key: String) -> String? {
    if let v = getenv(key) { let s = String(cString: v); return s.isEmpty ? nil : s }
    // Fallback to ~/AGENTS.env
    let home = FileManager.default.homeDirectoryForCurrentUser.path
    let path = home + "/AGENTS.env"
    guard let data = try? String(contentsOfFile: path, encoding: .utf8) else { return nil }
    for line in data.split(separator: "\n") {
        var s = line.trimmingCharacters(in: .whitespaces)
        if s.isEmpty || s.hasPrefix("#") { continue }
        if s.hasPrefix("export ") { s = String(s.dropFirst(7)).trimmingCharacters(in: .whitespaces) }
        if let eq = s.firstIndex(of: "=") {
            let k = s[..<eq].trimmingCharacters(in: .whitespacesAndNewlines).replacingOccurrences(of: "\"", with: "").replacingOccurrences(of: "'", with: "")
            var v = s[s.index(after: eq)...].trimmingCharacters(in: .whitespacesAndNewlines)
            if v.hasPrefix("\"") && v.hasSuffix("\"") { v = String(v.dropFirst().dropLast()) }
            if k == key { return String(v) }
        }
    }
    return nil
}

func sendTelegram(_ token: String, _ chatId: String, _ text: String) {
    guard let url = URL(string: "https://api.telegram.org/bot\(token)/sendMessage") else { return }
    var req = URLRequest(url: url); req.httpMethod = "POST"; req.setValue("application/json", forHTTPHeaderField: "Content-Type")
    let payload: [String: Any] = ["chat_id": chatId, "text": text, "disable_web_page_preview": true]
    req.httpBody = try? JSONSerialization.data(withJSONObject: payload)
    let sem = DispatchSemaphore(value: 0)
    URLSession.shared.dataTask(with: req) { _, _, _ in sem.signal() }.resume()
    _ = sem.wait(timeout: .now() + 15)
}

func requestAccess(_ store: EKEventStore) -> Bool {
    let sem = DispatchSemaphore(value: 0)
    var granted = false
    if #available(macOS 14.0, *) {
        store.requestFullAccessToEvents { g, _ in granted = g; sem.signal() }
    } else {
        store.requestAccess(to: .event) { g, _ in granted = g; sem.signal() }
    }
    _ = sem.wait(timeout: .now() + 60)
    return granted
}

func calendarsCmd() -> Int32 {
    let store = EKEventStore()
    guard requestAccess(store) else { fputs("Calendar access not granted\n", stderr); return 1 }
    let cals = store.calendars(for: .event)
    var out: [[String: Any]] = []
    for c in cals {
        out.append([
            "title": c.title,
            "id": c.calendarIdentifier,
            "sourceTitle": c.source?.title ?? "",
            "sourceType": c.source?.sourceType.rawValue ?? 0
        ])
    }
    let data = try! JSONSerialization.data(withJSONObject: ["calendars": out], options: [.prettyPrinted])
    FileHandle.standardOutput.write(data)
    return 0
}

func parseDate(_ s: String) -> Date? {
    // Accept YYYY-MM-DD or YYYY-MM-DDTHH:MM
    if s.count == 10 { let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"; f.timeZone = .current; return f.date(from: s) }
    let f1 = DateFormatter(); f1.dateFormat = "yyyy-MM-dd'T'HH:mm"; f1.timeZone = .current
    if let d = f1.date(from: s) { return d }
    let f2 = DateFormatter(); f2.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"; f2.timeZone = .current
    return f2.date(from: s)
}

func eventsListCmd(_ argv: Argv) -> Int32 {
    let store = EKEventStore(); guard requestAccess(store) else { fputs("Calendar access not granted\n", stderr); return 1 }
    let calNamesArg = argv.value(after: "--calendars")
    let includeNames: Set<String> = Set((calNamesArg ?? readEnv("INCLUDE_CALENDARS") ?? "").split(separator:",").map{ $0.trimmingCharacters(in: .whitespaces) }.filter{ !$0.isEmpty })
    let calIdsArg = argv.value(after: "--cal-ids")
    let includeIds: Set<String> = Set((calIdsArg ?? readEnv("INCLUDE_CALENDAR_IDS") ?? "").split(separator:",").map{ $0.trimmingCharacters(in: .whitespaces) }.filter{ !$0.isEmpty })
    var calendars = store.calendars(for: .event)
    if !includeIds.isEmpty { calendars = calendars.filter { includeIds.contains($0.calendarIdentifier) } }
    else if !includeNames.isEmpty { calendars = calendars.filter { includeNames.contains($0.title) } }
    if calendars.isEmpty { fputs("No matching calendars.\n", stderr) }
    let cal = Calendar.current
    var start: Date; var end: Date
    if argv.has("--today") { let s = cal.startOfDay(for: Date()); start = s; end = cal.date(byAdding: .day, value: 1, to: s)! }
    else if argv.has("--tomorrow") { let s0 = cal.startOfDay(for: Date()); let s = cal.date(byAdding: .day, value: 1, to: s0)!; start = s; end = cal.date(byAdding: .day, value: 1, to: s)! }
    else if let sArg = argv.value(after: "--start"), let eArg = argv.value(after: "--end"), let s = parseDate(sArg), let e = parseDate(eArg) { start = s; end = e }
    else { fputs("Provide --today/--tomorrow or --start and --end\n", stderr); return 2 }
    let predicate = store.predicateForEvents(withStart: start, end: end, calendars: calendars)
    var events = store.events(matching: predicate)
    events.sort { if $0.startDate != $1.startDate { return $0.startDate < $1.startDate }; return ($0.title ?? "") < ($1.title ?? "") }
    let jsonOut = argv.has("--json")
    if jsonOut {
        var items: [[String: Any]] = []
        for ev in events {
            items.append([
                "calendar": ev.calendar.title,
                "id": ev.eventIdentifier ?? "",
                "start": ev.startDate.timeIntervalSince1970,
                "end": ev.endDate.timeIntervalSince1970,
                "all_day": ev.isAllDay,
                "title": ev.title ?? "",
                "location": ev.location ?? ""
            ])
        }
        let data = try! JSONSerialization.data(withJSONObject: ["events": items], options: [.prettyPrinted])
        FileHandle.standardOutput.write(data)
    } else {
        let df = DateFormatter(); df.timeStyle = .short; df.dateStyle = .none
        for ev in events {
            if ev.isAllDay { print("- \(ev.calendar.title): (all-day) \(ev.title ?? "(No title)")") }
            else { print("- \(ev.calendar.title): \(df.string(from: ev.startDate))–\(df.string(from: ev.endDate))  \(ev.title ?? "(No title)")") }
        }
    }
    return 0
}

func findCalendar(store: EKEventStore, title: String) -> EKCalendar? { store.calendars(for: .event).first(where: { $0.title == title }) }

func eventsCreateCmd(_ argv: Argv) -> Int32 {
    let store = EKEventStore(); guard requestAccess(store) else { fputs("Calendar access not granted\n", stderr); return 1 }
    guard let calTitle = argv.value(after: "--calendar"), let title = argv.value(after: "--title") else { fputs("--calendar and --title required\n", stderr); return 2 }
    let isAllDay = argv.has("--all-day")
    var start: Date; var end: Date
    if isAllDay {
        guard let dateStr = argv.value(after: "--date"), let d = parseDate(dateStr) else { fputs("--date YYYY-MM-DD required for --all-day\n", stderr); return 2 }
        start = d; end = Calendar.current.date(byAdding: .day, value: 1, to: d)!
    } else {
        guard let sArg = argv.value(after: "--start"), let eArg = argv.value(after: "--end"), let s = parseDate(sArg), let e = parseDate(eArg) else { fputs("--start and --end required (YYYY-MM-DDTHH:MM)\n", stderr); return 2 }
        start = s; end = e
    }
    guard let cal = findCalendar(store: store, title: calTitle) else { fputs("Calendar not found: \(calTitle)\n", stderr); return 3 }
    let ev = EKEvent(eventStore: store)
    ev.calendar = cal; ev.title = title; ev.startDate = start; ev.endDate = end; ev.isAllDay = isAllDay
    if let loc = argv.value(after: "--location"), !loc.isEmpty { ev.location = loc }
    if let notes = argv.value(after: "--notes"), !notes.isEmpty { ev.notes = notes }
    if let urlStr = argv.value(after: "--url"), let u = URL(string: urlStr) { ev.url = u }
    do { try store.save(ev, span: .thisEvent) } catch { fputs("Save failed: \(error)\n", stderr); return 4 }
    print("{\"created_id\": \"\(ev.eventIdentifier ?? "")\"}")
    return 0
}

func eventsUpdateCmd(_ argv: Argv) -> Int32 {
    let store = EKEventStore(); guard requestAccess(store) else { fputs("Calendar access not granted\n", stderr); return 1 }
    guard let id = argv.value(after: "--id"), !id.isEmpty else { fputs("--id required\n", stderr); return 2 }
    guard let ev = store.event(withIdentifier: id) else { fputs("Event not found for id (may be out of cache window): \(id)\n", stderr); return 3 }
    if let t = argv.value(after: "--title") { ev.title = t }
    if let loc = argv.value(after: "--location") { ev.location = loc }
    if let notes = argv.value(after: "--notes") { ev.notes = notes }
    if let urlStr = argv.value(after: "--url") { ev.url = URL(string: urlStr) }
    if let sArg = argv.value(after: "--start"), let s = parseDate(sArg) { ev.startDate = s }
    if let eArg = argv.value(after: "--end"), let e = parseDate(eArg) { ev.endDate = e }
    if argv.has("--all-day") { ev.isAllDay = true }
    if argv.has("--not-all-day") { ev.isAllDay = false }
    do { try store.save(ev, span: .thisEvent) } catch { fputs("Update failed: \(error)\n", stderr); return 4 }
    print("{\"updated_id\": \"\(ev.eventIdentifier ?? "")\"}")
    return 0
}

func eventsDeleteCmd(_ argv: Argv) -> Int32 {
    let store = EKEventStore(); guard requestAccess(store) else { fputs("Calendar access not granted\n", stderr); return 1 }
    guard let id = argv.value(after: "--id"), !id.isEmpty else { fputs("--id required\n", stderr); return 2 }
    guard let ev = store.event(withIdentifier: id) else { fputs("Event not found: \(id)\n", stderr); return 3 }
    do { try store.remove(ev, span: .thisEvent) } catch { fputs("Delete failed: \(error)\n", stderr); return 4 }
    print("{\"deleted_id\": \"\(id)\"}")
    return 0
}

func eventsBulkCreateCmd(_ argv: Argv) -> Int32 {
    let store = EKEventStore(); guard requestAccess(store) else { fputs("Calendar access not granted\n", stderr); return 1 }
    guard let filePath = argv.value(after: "--file") else { fputs("--file <path to JSONL> required\n", stderr); return 2 }
    let defaultCalendar = argv.value(after: "--calendar")
    let dryRun = argv.has("--dry-run")
    let fm = FileManager.default
    guard fm.fileExists(atPath: filePath) else { fputs("File not found: \(filePath)\n", stderr); return 2 }
    guard let raw = try? String(contentsOfFile: filePath, encoding: .utf8) else { fputs("Failed to read file\n", stderr); return 3 }
    let lines = raw.split(separator: "\n", omittingEmptySubsequences: false)
    var results: [[String: Any]] = []
    let calendars = store.calendars(for: .event)
    func findCal(_ title: String) -> EKCalendar? { calendars.first(where: { $0.title == title }) }
    var idx = 0
    for line in lines {
        idx += 1
        let sline = line.trimmingCharacters(in: .whitespacesAndNewlines)
        if sline.isEmpty || sline.hasPrefix("#") { continue }
        guard let data = sline.data(using: .utf8) else { continue }
        guard let obj = try? JSONSerialization.jsonObject(with: data, options: []) as? [String: Any] else {
            results.append(["line": idx, "error": "invalid json"])
            continue
        }
        let calTitle = (obj["calendar"] as? String) ?? defaultCalendar
        guard let calTitleUnwrapped = calTitle, let cal = findCal(calTitleUnwrapped) else {
            results.append(["line": idx, "error": "calendar not found", "calendar": calTitle ?? "(none)"])
            continue
        }
        let title = (obj["title"] as? String) ?? (obj["summary"] as? String) ?? "(No title)"
        var isAllDay = (obj["all_day"] as? Bool) ?? false
        var start: Date?
        var end: Date?
        if let dateStr = obj["date"] as? String { start = parseDate(dateStr); if let s = start { end = Calendar.current.date(byAdding: .day, value: 1, to: s); isAllDay = true } }
        if start == nil, let sStr = obj["start"] as? String { start = parseDate(sStr); if sStr.count == 10 { isAllDay = true } }
        if end == nil, let eStr = obj["end"] as? String { end = parseDate(eStr) }
        guard let sDate = start else { results.append(["line": idx, "error": "missing/invalid start or date", "title": title]); continue }
        var eDate = end
        if eDate == nil { eDate = isAllDay ? Calendar.current.date(byAdding: .day, value: 1, to: sDate) : Calendar.current.date(byAdding: .hour, value: 1, to: sDate) }
        guard let eDateUnwrapped = eDate else { results.append(["line": idx, "error": "invalid end", "title": title]); continue }
        let ev = EKEvent(eventStore: store)
        ev.calendar = cal; ev.title = title; ev.startDate = sDate; ev.endDate = eDateUnwrapped; ev.isAllDay = isAllDay
        if let loc = obj["location"] as? String, !loc.isEmpty { ev.location = loc }
        if let notes = obj["notes"] as? String, !notes.isEmpty { ev.notes = notes }
        if let urlStr = obj["url"] as? String, let u = URL(string: urlStr) { ev.url = u }
        if dryRun {
            results.append(["line": idx, "dry_run": true, "title": title, "calendar": calTitleUnwrapped])
            continue
        }
        do { try store.save(ev, span: .thisEvent) }
        catch { results.append(["line": idx, "error": "save failed", "reason": String(describing: error), "title": title]); continue }
        results.append(["line": idx, "created_id": ev.eventIdentifier ?? "", "title": title, "calendar": calTitleUnwrapped])
    }
    let out = try! JSONSerialization.data(withJSONObject: ["results": results], options: [.prettyPrinted])
    FileHandle.standardOutput.write(out)
    return 0
}

func eventsFindCmd(_ argv: Argv) -> Int32 {
    let store = EKEventStore(); guard requestAccess(store) else { fputs("Calendar access not granted\n", stderr); return 1 }
    // Calendars filter
    let calNamesArg = argv.value(after: "--calendars")
    let includeNames: Set<String> = Set((calNamesArg ?? readEnv("INCLUDE_CALENDARS") ?? "").split(separator:",").map{ $0.trimmingCharacters(in: .whitespaces) }.filter{ !$0.isEmpty })
    let calIdsArg = argv.value(after: "--cal-ids")
    let includeIds: Set<String> = Set((calIdsArg ?? readEnv("INCLUDE_CALENDAR_IDS") ?? "").split(separator:",").map{ $0.trimmingCharacters(in: .whitespaces) }.filter{ !$0.isEmpty })
    var calendars = store.calendars(for: .event)
    if !includeIds.isEmpty { calendars = calendars.filter { includeIds.contains($0.calendarIdentifier) } }
    else if !includeNames.isEmpty { calendars = calendars.filter { includeNames.contains($0.title) } }
    // Date range
    let cal = Calendar.current
    var start: Date; var end: Date
    if argv.has("--today") { let s = cal.startOfDay(for: Date()); start = s; end = cal.date(byAdding: .day, value: 1, to: s)! }
    else if argv.has("--tomorrow") { let s0 = cal.startOfDay(for: Date()); let s = cal.date(byAdding: .day, value: 1, to: s0)!; start = s; end = cal.date(byAdding: .day, value: 1, to: s)! }
    else if let dateStr = argv.value(after: "--date"), let d = parseDate(dateStr) { start = d; end = cal.date(byAdding: .day, value: 1, to: d)! }
    else if let sArg = argv.value(after: "--start"), let eArg = argv.value(after: "--end"), let s = parseDate(sArg), let e = parseDate(eArg) { start = s; end = e }
    else { fputs("Provide --today/--tomorrow or --date or --start/--end\n", stderr); return 2 }
    // Fetch events
    let predicate = store.predicateForEvents(withStart: start, end: end, calendars: calendars)
    var events = store.events(matching: predicate)
    // Title filter
    if let exact = argv.value(after: "--title"), !exact.isEmpty {
        events = events.filter { ($0.title ?? "") == exact }
    } else if let contains = argv.value(after: "--title-contains"), !contains.isEmpty {
        let needle = contains.lowercased()
        events = events.filter { ($0.title ?? "").lowercased().contains(needle) }
    }
    events.sort { if $0.startDate != $1.startDate { return $0.startDate < $1.startDate }; return ($0.title ?? "") < ($1.title ?? "") }
    let iso = ISO8601DateFormatter(); iso.timeZone = .current
    var items: [[String: Any]] = []
    for ev in events {
        items.append([
            "calendar": ev.calendar.title,
            "id": ev.eventIdentifier ?? "",
            "start": iso.string(from: ev.startDate),
            "end": iso.string(from: ev.endDate),
            "all_day": ev.isAllDay,
            "title": ev.title ?? "",
            "location": ev.location ?? ""
        ])
    }
    let data = try! JSONSerialization.data(withJSONObject: ["events": items], options: [.prettyPrinted])
    FileHandle.standardOutput.write(data)
    return 0
}

func digestCmd(_ argv: Argv) -> Int32 {
    let store = EKEventStore(); guard requestAccess(store) else { fputs("Calendar access not granted\n", stderr); return 1 }
    let day = argv.value(after: "--day") ?? "today"
    let rangeDays = Int(argv.value(after: "--range-days") ?? readEnv("RANGE_DAYS") ?? "0") ?? 0
    let include = argv.value(after: "--calendars") ?? readEnv("INCLUDE_CALENDARS") ?? ""
    let includeNames = Set(include.split(separator:",").map{ $0.trimmingCharacters(in: .whitespaces) }.filter{ !$0.isEmpty })
    let includeIds = Set((argv.value(after: "--cal-ids") ?? readEnv("INCLUDE_CALENDAR_IDS") ?? "").split(separator:",").map{ $0.trimmingCharacters(in: .whitespaces) }.filter{ !$0.isEmpty })
    var calendars = store.calendars(for: .event)
    if !includeIds.isEmpty { calendars = calendars.filter { includeIds.contains($0.calendarIdentifier) } }
    else if !includeNames.isEmpty { calendars = calendars.filter { includeNames.contains($0.title) } }
    let cal = Calendar.current
    let baseStart = cal.startOfDay(for: Date())
    let offset = (day == "tomorrow") ? 1 : 0
    let startOfDay = cal.date(byAdding: .day, value: offset, to: baseStart)!
    let endDate = cal.date(byAdding: .day, value: rangeDays + 1, to: startOfDay)!
    let predicate = store.predicateForEvents(withStart: startOfDay, end: endDate, calendars: calendars)
    var events = store.events(matching: predicate)
    events.sort { if $0.startDate != $1.startDate { return $0.startDate < $1.startDate }; return ($0.title ?? "") < ($1.title ?? "") }
    let dfDate = DateFormatter(); dfDate.dateStyle = .full
    let dfTime = DateFormatter(); dfTime.timeStyle = .short
    var header: String
    if rangeDays == 0 {
        header = offset == 0 ? "📅 Today’s schedule — \(dfDate.string(from: startOfDay))" : "📅 Tomorrow’s schedule — \(dfDate.string(from: startOfDay))"
    } else {
        let endHdr = cal.date(byAdding: .day, value: rangeDays, to: startOfDay)!
        header = "📅 \(dfDate.string(from: startOfDay)) → \(dfDate.string(from: endHdr))"
    }
    var byCal: [String: [EKEvent]] = [:]
    for ev in events { byCal[ev.calendar.title, default: []].append(ev) }
    var lines: [String] = [header, ""]
    for calObj in calendars {
        let name = calObj.title
        guard let group = byCal[name], !group.isEmpty else { continue }
        lines.append("• \(name):")
        for ev in group {
            let title = (ev.title?.isEmpty == false) ? ev.title! : "(No title)"
            if ev.isAllDay { lines.append("  – (all‑day) \(title)") }
            else {
                let t1 = dfTime.string(from: ev.startDate); let t2 = dfTime.string(from: ev.endDate)
                var line = "  – \(t1)–\(t2)  \(title)"
                if let loc = ev.location, !loc.isEmpty { line += " (\(loc))" }
                lines.append(line)
            }
        }
        lines.append("")
    }
    let text = lines.joined(separator: "\n")
    if let token = readEnv("TELEGRAM_BOT_TOKEN"), let chatId = readEnv("TELEGRAM_CHAT_ID") {
        // Split long messages
        let maxLen = 3500
        if text.count <= maxLen { sendTelegram(token, chatId, text) }
        else {
            var idx = text.startIndex
            while idx < text.endIndex {
                let endIdx = text.index(idx, offsetBy: maxLen, limitedBy: text.endIndex) ?? text.endIndex
                sendTelegram(token, chatId, String(text[idx..<endIdx])); idx = endIdx
            }
        }
        print("{\"sent\": true, \"day\": \"\(day)\", \"range_days\": \(rangeDays)}")
    } else {
        print(text)
    }
    return 0
}

func usage() {
    let msg = """
    ekcal — EventKit (macOS Calendar) CLI
    Usage:
      ekcal calendars
      ekcal events list [--today|--tomorrow|--start YYYY-MM-DD|YYYY-MM-DDTHH:MM --end YYYY-MM-DD|YYYY-MM-DDTHH:MM] [--calendars 'A,B'|--cal-ids 'ID1,ID2'] [--json]
      ekcal events find [--today|--tomorrow|--date YYYY-MM-DD|--start ... --end ...] [--calendars 'A,B'|--cal-ids 'ID1,ID2'] [--title 'Exact'|--title-contains 'Substr']
      ekcal events create --calendar 'Name' --title 'Text' [--all-day --date YYYY-MM-DD | --start YYYY-MM-DDTHH:MM --end YYYY-MM-DDTHH:MM] [--location 'L'] [--notes 'N'] [--url 'U']
      ekcal events bulk-create --file /path/events.jsonl [--calendar 'Default'] [--dry-run]
      ekcal events update --id <EVENT_ID> [--title T] [--start ...] [--end ...] [--location L] [--notes N] [--url U] [--all-day|--not-all-day]
      ekcal events delete --id <EVENT_ID>
      ekcal digest [--day today|tomorrow] [--range-days N] [--calendars 'A,B'|--cal-ids 'ID1,ID2']
      ekcal digest-week [--calendars 'A,B'|--cal-ids 'ID1,ID2']
    """
    print(msg)
}

func main() -> Int32 {
    var args = ProcessInfo.processInfo.arguments
    _ = args.removeFirst() // program name
    let argv = Argv(args: args)
    guard let cmd = args.first else { usage(); return 1 }
    if cmd == "calendars" { return calendarsCmd() }
    else if cmd == "events" {
        guard args.count >= 2 else { usage(); return 2 }
        let sub = args[1]
        let subArgv = Argv(args: Array(args.dropFirst(2)))
        switch sub {
        case "list": return eventsListCmd(subArgv)
        case "find": return eventsFindCmd(subArgv)
        case "create": return eventsCreateCmd(subArgv)
        case "update": return eventsUpdateCmd(subArgv)
        case "delete": return eventsDeleteCmd(subArgv)
        case "bulk-create": return eventsBulkCreateCmd(subArgv)
        default: usage(); return 2
        }
    } else if cmd == "digest" { return digestCmd(Argv(args: Array(args.dropFirst(1)))) }
    else if cmd == "digest-week" { var rest = Array(args.dropFirst(1)); rest.append(contentsOf: ["--range-days", "7"]); return digestCmd(Argv(args: rest)) }
    else { usage(); return 1 }
}

exit(main())
