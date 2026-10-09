import AppKit
import WebKit
import Darwin

let bundleID = "local.calmtranslate.desktop"

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler {
    var window: NSWindow!
    var web: WKWebView?
    var backend: Process?
    var captureChild: Process?
    var captureInput: Pipe?
    var input: Pipe?
    var output: Pipe?
    var port: Int = 0
    var generation = 0
    var lockFD: Int32 = -1
    var quitting = false
    var verification: VerificationRunner?
    let defaults = CommandLine.arguments.contains("--verify-lifecycle") ? UserDefaults(suiteName:"local.calmtranslate.desktop.verification")! : UserDefaults.standard
    let dataRoot = CommandLine.arguments.contains("--verify-lifecycle") ? URL(fileURLWithPath:"/tmp/calm-translate-verification-data",isDirectory:true) : FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("Calm Translate", isDirectory:true)

    func applicationDidFinishLaunching(_ notification: Notification) {
        do { try FileManager.default.createDirectory(at:dataRoot,withIntermediateDirectories:true,attributes:[.posixPermissions:0o700]) }
        catch { fatalUI("Не удалось открыть папку данных приложения."); return }
        lockFD = Darwin.open(dataRoot.appendingPathComponent("desktop.lock").path, O_CREAT | O_RDWR, 0o600)
        guard lockFD >= 0, flock(lockFD,LOCK_EX | LOCK_NB)==0 else {
            NSRunningApplication.runningApplications(withBundleIdentifier:bundleID).first(where:{$0.processIdentifier != getpid()})?.activate(options:[])
            NSApp.terminate(nil); return
        }
        makeMenus()
        makeWindow()
        startBackend()
        NSApp.activate(ignoringOtherApps:true)
    }

    func makeWindow() {
        if window == nil {
            window=NSWindow(contentRect:NSRect(x:0,y:0,width:1180,height:820),styleMask:[.titled,.closable,.miniaturizable,.resizable],backing:.buffered,defer:false)
            window.title="Trailk"
            window.minSize=NSSize(width:540,height:580)
            window.isReleasedWhenClosed=false
            window.delegate=self
            window.center()
            window.setFrameAutosaveName("CalmMainWindow")
        }
        window.makeKeyAndOrderFront(nil)
    }

    func makeMenus() {
        let bar=NSMenu(); NSApp.mainMenu=bar
        func section(_ name:String)->NSMenu {
            let item=NSMenuItem();bar.addItem(item)
            let menu=NSMenu(title:name);item.submenu=menu;return menu
        }
        func item(_ menu:NSMenu,_ title:String,_ action:Selector?,_ key:String="",_ target:AnyObject?=nil) {
            let i=NSMenuItem(title:title,action:action,keyEquivalent:key);i.target=target;menu.addItem(i)
        }
        let app=section("Trailk")
        item(app,"О Trailk",#selector(about),"",self)
        item(app,"Настройки чтения…",#selector(settings),",",self)
        app.addItem(.separator())
        item(app,"Скрыть Trailk",#selector(NSApplication.hide(_:)),"h",NSApp)
        app.addItem(.separator())
        item(app,"Завершить Trailk",#selector(NSApplication.terminate(_:)),"q",NSApp)
        let edit=section("Правка")
        item(edit,"Отменить",Selector(("undo:")),"z")
        item(edit,"Вырезать",#selector(NSText.cut(_:)),"x")
        item(edit,"Копировать",#selector(NSText.copy(_:)),"c")
        item(edit,"Вставить",#selector(NSText.paste(_:)),"v")
        item(edit,"Выделить всё",#selector(NSText.selectAll(_:)),"a")
        let view=section("Вид")
        item(view,"К истории перевода",#selector(captions),"1",self)
        item(view,"К моей мысли",#selector(reply),"2",self)
        item(view,"Увеличить текст",#selector(larger),"+",self)
        item(view,"Уменьшить текст",#selector(smaller),"-",self)
        item(view,"Пауза прокрутки",#selector(pause),"p",self)
        item(view,"К новым строкам",#selector(follow),"j",self)
        let windows=section("Окно");NSApp.windowsMenu=windows
        item(windows,"Открыть окно",#selector(reopen),"0",self)
        item(windows,"Свернуть",#selector(NSWindow.performMiniaturize(_:)),"m")
        item(windows,"Закрыть окно",#selector(NSWindow.performClose(_:)),"w")
    }

    func loading(_ text:String, retry:Bool=false) {
        let box=NSView(frame:NSRect(x:0,y:0,width:1000,height:700))
        let label=NSTextField(wrappingLabelWithString:text)
        label.font=NSFont.systemFont(ofSize:19);label.translatesAutoresizingMaskIntoConstraints=false
        box.addSubview(label)
        NSLayoutConstraint.activate([label.centerXAnchor.constraint(equalTo:box.centerXAnchor),label.centerYAnchor.constraint(equalTo:box.centerYAnchor),label.widthAnchor.constraint(lessThanOrEqualToConstant:640)])
        if retry {
            let b=NSButton(title:"Повторить запуск локального сервера",target:self,action:#selector(retryBackend));b.translatesAutoresizingMaskIntoConstraints=false;box.addSubview(b)
            NSLayoutConstraint.activate([b.centerXAnchor.constraint(equalTo:box.centerXAnchor),b.topAnchor.constraint(equalTo:label.bottomAnchor,constant:24)])
        }
        window.contentView=box
    }

    func startBackend() {
        guard backend == nil, !quitting else{return}
        generation += 1;let current=generation
        loading("Запускаю локальный интерфейс…\nЗвук и платные API не запускаются.")
        guard let resources=Bundle.main.resourceURL else {loading("Ресурсы приложения недоступны.");return}
        let binary=resources.appendingPathComponent("backend/calm-backend")
        let helper=resources.appendingPathComponent("keychain-bridge")
        guard FileManager.default.isExecutableFile(atPath:binary.path),FileManager.default.isExecutableFile(atPath:helper.path) else {loading("Приложение собрано не полностью. Переустановите подготовленный .app.");return}
        let process=Process();let stdinPipe=Pipe();let stdoutPipe=Pipe()
        process.executableURL=binary
        process.environment=["PATH":"/usr/bin:/bin","CALM_DATA_ROOT":dataRoot.path,"CALM_KEYCHAIN_BRIDGE":helper.path,"PYTHONUTF8":"1"]
        if verification != nil{process.environment?["CALM_VERIFY_OFFLINE"]="1"}
        process.standardInput=stdinPipe;process.standardOutput=stdoutPipe;process.standardError=FileHandle.nullDevice
        backend=process;input=stdinPipe;output=stdoutPipe
        var pending=Data()
        stdoutPipe.fileHandleForReading.readabilityHandler={ [weak self] handle in
            let chunk=handle.availableData
            if chunk.isEmpty {handle.readabilityHandler=nil;return}
            pending.append(chunk)
            if pending.count>8192 {handle.readabilityHandler=nil;DispatchQueue.main.async{self?.failed(current,"Локальный сервер вернул некорректный ответ.")};return}
            guard let newline=pending.firstIndex(of:10) else{return}
            let line=pending.prefix(upTo:newline);handle.readabilityHandler=nil
            guard let value=try? JSONSerialization.jsonObject(with:line) as? [String:Any],let valuePort=value["port"] as? Int,value["ready"] as? Bool==true,(1024...65535).contains(valuePort) else {DispatchQueue.main.async{self?.failed(current,"Локальный сервер не подтвердил запуск.")};return}
            DispatchQueue.main.async{guard let self=self,self.generation==current,self.backend===process else{return};self.port=valuePort;self.showWeb()}
        }
        process.terminationHandler={ [weak self] _ in DispatchQueue.main.async {
            guard let self=self,self.generation==current,self.backend===process else{return}
            self.stopCapture();self.backend=nil;self.input=nil;self.output=nil;self.port=0
            self.web?.configuration.userContentController.removeScriptMessageHandler(forName:"settings");self.web?.configuration.userContentController.removeScriptMessageHandler(forName:"capture");self.web?.stopLoading();self.web=nil
            if !self.quitting,self.window.isVisible {self.loading("Локальный сервер остановился. Данные Keychain сохранены. Автоматических запросов нет.",retry:true)}
        }}
        do {try process.run()}
        catch {failed(current,"Не удалось запустить встроенный сервер. Никаких API-запросов не было.");return}
        DispatchQueue.main.asyncAfter(deadline:.now()+12) {[weak self] in
            guard let self=self,self.generation==current,self.port==0,self.backend != nil else{return}
            self.failed(current,"Встроенный сервер не запустился за 12 секунд. Можно повторить вручную.")
        }
    }

    func failed(_ current:Int,_ text:String) {
        guard generation==current else{return};stopBackend();loading(text,retry:true)
    }

    func showWeb() {
        let config=WKWebViewConfiguration()
        config.mediaTypesRequiringUserActionForPlayback = .all
        config.websiteDataStore = .nonPersistent()
        config.userContentController.add(self,name:"settings")
        config.userContentController.add(self,name:"capture")
        let prefs=validatedPreferences(defaults.dictionary(forKey:"reading") ?? [:])
        let data=(try? JSONSerialization.data(withJSONObject:prefs,options:[.sortedKeys])) ?? Data("{}".utf8)
        let script="window.calmPreferences="+(String(data:data,encoding:.utf8) ?? "{}")+";window.calmVerification="+(verification != nil ? "true" : "false")+";"
        config.userContentController.addUserScript(WKUserScript(source:script,injectionTime:.atDocumentStart,forMainFrameOnly:true))
        let view=WKWebView(frame:.zero,configuration:config)
        view.navigationDelegate=self;view.uiDelegate=self
        web=view;window.contentView=view
        view.load(URLRequest(url:URL(string:"http://127.0.0.1:\(port)/")!))
    }

    func validatedPreferences(_ value:[String:Any])->[String:Any] {
        var safe:[String:Any]=[:]
        if let version=value["uiVersion"] as? Int,[1,2].contains(version){safe["uiVersion"]=version}
        if let n=value["font"] as? Int,(18...38).contains(n){safe["font"]=n}
        if let mode=value["mode"] as? String,["replay","live"].contains(mode){safe["mode"]=mode}
        if let follow=value["follow"] as? Bool{safe["follow"]=follow}
        if let theme=value["theme"] as? String,["system","dark","light"].contains(theme){safe["theme"]=theme}
        if let context=value["context"] as? Bool{safe["context"]=context}
        if let minutes=value["minutes"] as? Int,[10,30,60,90].contains(minutes){safe["minutes"]=minutes}
        return safe
    }

    func userContentController(_ userContentController:WKUserContentController,didReceive message:WKScriptMessage) {
        guard message.frameInfo.isMainFrame,message.frameInfo.securityOrigin.host=="127.0.0.1",message.frameInfo.securityOrigin.port==port,let value=message.body as? [String:Any] else{return}
        if message.name=="capture" {if value["action"] as? String=="open" {openCapture(session:value["session"] as? [String:Any])} else if value["action"] as? String=="stop"{stopCapture()};return}
        defaults.set(validatedPreferences(value),forKey:"reading")
    }

    func webView(_ webView:WKWebView,decidePolicyFor navigationAction:WKNavigationAction,decisionHandler:@escaping(WKNavigationActionPolicy)->Void) {
        guard let url=navigationAction.request.url,url.scheme=="http",url.host=="127.0.0.1",url.port==port,navigationAction.targetFrame?.isMainFrame==true else {decisionHandler(.cancel);return}
        decisionHandler(.allow)
    }
    func webView(_ webView:WKWebView,didFinish navigation:WKNavigation!){verification?.ready(webView)}
    func webView(_ webView:WKWebView,didFailProvisionalNavigation navigation:WKNavigation!,withError error:Error){loading("Не удалось открыть локальное окно. Повтор запуска выполняется только вручную.",retry:true)}
    func webViewWebContentProcessDidTerminate(_ webView:WKWebView){loading("Процесс интерфейса завершился. Можно повторить локальный запуск; ключ и лимиты сохранены.",retry:true)}
    func webView(_ webView:WKWebView,requestMediaCapturePermissionFor origin:WKSecurityOrigin,initiatedByFrame frame:WKFrameInfo,type:WKMediaCaptureType,decisionHandler:@escaping(WKPermissionDecision)->Void){decisionHandler(.deny)}

    func openCapture(session:[String:Any]?=nil) {
        guard verification==nil,captureChild==nil,let resources=Bundle.main.resourceURL else{return}
        var sessionJSON:String?
        if let decision=session {
            guard decision["approved"] as? Bool==true,decision["resume_audio"] as? Bool==true,decision["source"] as? String=="zoom",[2,3,4].contains(decision["schema_version"] as? Int ?? 0),decision["microphone"] as? Bool==false,decision["private_call_capture"] as? Bool==true,
                  let socket=decision["socket_path"] as? String,socket.hasPrefix(dataRoot.appendingPathComponent("runtime").path+"/"),socket.hasSuffix(".sock"),
                  let expiry=decision["expires_unix"] as? Double,expiry>Date().timeIntervalSince1970,let data=try? JSONSerialization.data(withJSONObject:decision),let text=String(data:data,encoding:.utf8) else{return}
            sessionJSON=text
        } else {
            guard !FileManager.default.fileExists(atPath:dataRoot.appendingPathComponent("AUDIO-DO-NOT-PLAY.json").path),
                  let bytes=try? Data(contentsOf:dataRoot.appendingPathComponent("CAPTURE-APPROVAL.json")),
                  let decision=try? JSONSerialization.jsonObject(with:bytes) as? [String:Any],decision["approved"] as? Bool==true,
                  ["public_sample","zoom"].contains(decision["source"] as? String ?? "") else{return}
        }
        let process=Process(),pipe=Pipe()
        process.executableURL=resources.appendingPathComponent("Calm Capture.app/Contents/MacOS/CalmCapture")
        process.environment=["PATH":"/usr/bin:/bin","CALM_DATA_ROOT":dataRoot.path,"CALM_MANAGED_CHILD":"1"]
        if let approval=sessionJSON{process.environment?["CALM_SESSION_APPROVAL"]=approval}
        process.standardInput=pipe;process.standardOutput=FileHandle.nullDevice;process.standardError=FileHandle.nullDevice
        captureChild=process;captureInput=pipe
        process.terminationHandler={[weak self] _ in DispatchQueue.main.async {guard self?.captureChild===process else{return};self?.captureChild=nil;self?.captureInput=nil}}
        do {try process.run()} catch {captureChild=nil;captureInput=nil;js("document.getElementById('capture-status').textContent='Встроенный helper не запустился. Захват и звук не начинались.';")}
    }
    func stopCapture() {
        let old=captureChild;captureChild=nil
        try? captureInput?.fileHandleForWriting.close();captureInput=nil
        if let child=old,child.isRunning {DispatchQueue.global().async {for _ in 0..<20 {if !child.isRunning{return};Thread.sleep(forTimeInterval:0.05)};if child.isRunning{child.terminate()}}}
    }
    func stopBackend() {
        stopCapture()
        generation += 1;port=0
        let old=backend;backend=nil
        output?.fileHandleForReading.readabilityHandler=nil
        try? input?.fileHandleForWriting.write(contentsOf:Data("stop\n".utf8));try? input?.fileHandleForWriting.close()
        input=nil;output=nil
        web?.configuration.userContentController.removeScriptMessageHandler(forName:"settings")
        web?.configuration.userContentController.removeScriptMessageHandler(forName:"capture")
        web?.stopLoading();web=nil
        guard let child=old,child.isRunning else{return}
        DispatchQueue.global().async {
            // Only this Process's child. No global pkill, no other app changes.
            for _ in 0..<20 {if !child.isRunning{return};Thread.sleep(forTimeInterval:0.05)}
            if child.isRunning{child.terminate()}
            for _ in 0..<20 {if !child.isRunning{return};Thread.sleep(forTimeInterval:0.05)}
            if child.isRunning{kill(child.processIdentifier,SIGKILL)}
        }
    }

    func windowWillClose(_ notification:Notification){stopBackend()}
    func applicationShouldTerminate(_ sender:NSApplication)->NSApplication.TerminateReply {
        quitting=true;let child=backend;stopBackend()
        guard child?.isRunning==true else{return .terminateNow}
        DispatchQueue.global().async {
            for _ in 0..<50 {if child?.isRunning != true{break};Thread.sleep(forTimeInterval:0.05)}
            DispatchQueue.main.async{NSApp.reply(toApplicationShouldTerminate:true)}
        };return .terminateLater
    }
    func applicationShouldHandleReopen(_ sender:NSApplication,hasVisibleWindows flag:Bool)->Bool{reopen();return true}
    func applicationWillTerminate(_ notification:Notification){if lockFD>=0{flock(lockFD,LOCK_UN);Darwin.close(lockFD)}}
    func fatalUI(_ text:String){let alert=NSAlert();alert.messageText=text;alert.runModal();NSApp.terminate(nil)}
    @objc func reopen(){makeWindow();if backend==nil{startBackend()};NSApp.activate(ignoringOtherApps:true)}
    @objc func retryBackend(){stopBackend();startBackend()}
    func js(_ source:String){web?.evaluateJavaScript(source,completionHandler:nil)}
    @objc func settings(){js("document.getElementById('font').scrollIntoView({block:'center'});document.getElementById('font').focus();")}
    @objc func captions(){js("document.getElementById('history').focus();")}
    @objc func reply(){js("document.getElementById('intent').scrollIntoView({block:'center'});document.getElementById('intent').focus();")}
    @objc func larger(){js("window.calmChangeFont(2);")}
    @objc func smaller(){js("window.calmChangeFont(-2);")}
    @objc func pause(){js("document.getElementById('pause-reading').click();")}
    @objc func follow(){js("document.getElementById('follow').click();")}
    @objc func about(){let a=NSAlert();a.messageText="Trailk";a.informativeText="Локальное окно для спокойного чтения английского → русского и подготовки своей мысли.\n\nВерсия 1.0 · Apple Silicon\nЗвук остановлен по вашей просьбе. Длительный Zoom-звонок пока не проверен.\nОфлайн replay проверяет интерфейс, не качество перевода.";a.runModal()}
}

let app=NSApplication.shared
app.setActivationPolicy(.regular)
let delegate=AppDelegate()
app.delegate=delegate
if CommandLine.arguments.contains("--verify-lifecycle"){delegate.verification=VerificationRunner(delegate:delegate)}
app.run()
