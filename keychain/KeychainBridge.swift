import Foundation
import Security
import LocalAuthentication

// Fixed service/account only. Save is exclusively a user-submitted credential;
// no API request, key generation, credential enumeration, clipboard, or auth logging.
let service = "local.calmtranslate.openai"
let account = "user-entered"
let query: [String: Any] = [kSecClass as String:kSecClassGenericPassword,
                           kSecAttrService as String:service,kSecAttrAccount as String:account]
func result(_ status:OSStatus,_ stored:Bool? = nil) {
    var value:[String:Any] = ["ok":status == errSecSuccess,"status":Int(status)]
    if let stored {value["stored"] = stored}
    let data = try! JSONSerialization.data(withJSONObject:value)
    FileHandle.standardOutput.write(data)
}
let action = CommandLine.arguments.dropFirst().first ?? ""
switch action {
case "save":
    var key = FileHandle.standardInput.readDataToEndOfFile()
    defer {key.resetBytes(in:0..<key.count)}
    guard (20...512).contains(key.count),let text=String(data:key,encoding:.utf8),
          !text.contains(where:{$0.isWhitespace}) else {result(errSecParam);exit(1)}
    var item=query;item[kSecValueData as String]=key
    item[kSecAttrLabel as String]="Calm Translate · OpenAI key (entered by user)"
    var status=SecItemAdd(item as CFDictionary,nil)
    if status == errSecDuplicateItem {
        status=SecItemUpdate(query as CFDictionary,[kSecValueData as String:key] as CFDictionary)
    }
    result(status)
case "status":
    var item=query;item[kSecReturnAttributes as String]=true
    item[kSecMatchLimit as String]=kSecMatchLimitOne
    let context=LAContext();context.interactionNotAllowed=true
    item[kSecUseAuthenticationContext as String]=context
    var attributes:CFTypeRef?
    let status=SecItemCopyMatching(item as CFDictionary,&attributes)
    attributes=nil
    result(status == errSecItemNotFound ? errSecSuccess:status,status == errSecSuccess)
case "load-for-client":
    // Called only by local client code during an explicitly initiated run.
    // Agent tools must NEVER invoke this action or inspect its stdout.
    var item=query;item[kSecReturnData as String]=true;item[kSecMatchLimit as String]=kSecMatchLimitOne
    var value:CFTypeRef?
    let status=SecItemCopyMatching(item as CFDictionary,&value)
    guard status == errSecSuccess,var key=value as? Data else {value=nil;exit(2)}
    value=nil;FileHandle.standardOutput.write(key);key.resetBytes(in:0..<key.count)
case "delete-by-user":
    // Explicit user's Delete button only; never teardown/TTL cleanup.
    let status=SecItemDelete(query as CFDictionary)
    result(status == errSecItemNotFound ? errSecSuccess:status)
default:
    result(errSecParam);exit(1)
}
