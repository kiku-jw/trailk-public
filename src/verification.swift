// Development-only, deliberate --verify-lifecycle: live WK rendering with synthetic fixtures.
// Does not read Keychain, enable capture or invoke provider endpoints.
import AppKit
import WebKit

final class VerificationRunner {
    weak var owner:AppDelegate?
    var phase=0
    var checks:[[String:Any]]=[]
    var oldChild:Process?
    var anchor:Double=0
    let proof=URL(fileURLWithPath:"/tmp/calm-translate-verification-proof",isDirectory:true)
    init(delegate:AppDelegate){owner=delegate;try? FileManager.default.createDirectory(at:proof,withIntermediateDirectories:true)}
    func check(_ name:String,_ passed:Bool,_ detail:Any=""){checks.append(["name":name,"passed":passed,"detail":detail])}
    func evaluate(_ js:String,_ callback:@escaping([String:Any])->Void) {
        guard let view=owner?.web else{finish(false);return}
        view.evaluateJavaScript(js){[weak self] value,error in
            guard error==nil,let object=value as? [String:Any] else {self?.check("web_js",false,"Script evaluation failed");self?.finish(false);return};callback(object)
        }
    }
    func later(_ seconds:Double,_ block:@escaping()->Void){DispatchQueue.main.asyncAfter(deadline:.now()+seconds,execute:block)}
    func ready(_ view:WKWebView){later(0.8){[weak self] in if self?.phase==0 {self?.verifyStartUX()} else {self?.step()}}}
    func verifyStartUX(){
        guard let app=owner else{finish(false);return}
        app.js("window.calmMeasureLatency=true;window.verifyFetch=window.fetch;window.verifyStarts=0;window.verifyStops=0;window.fetch=async (url,opts)=>{if(url==='/api/start'){window.verifyStarts++;if(window.verifyStartError)return new Response(JSON.stringify({error:'Synthetic validation error'}),{status:400});await new Promise(r=>setTimeout(r,800));return new Response(JSON.stringify({native_session:null}));}if(url==='/api/stop'){window.verifyStops++;return new Response('{}');}return window.verifyFetch(url,opts);};window.verifyState={running:false,configured:false,events:[],settings:{budget_confirmed:false,capture_allowed:true,cloud_allowed:true},instance_id:window.calmLiveState?.instance_id||'start-fixture'};window.calmStartVerify.setState(window.verifyState);window.scrollTo(0,0);window.calmStartVerify.start();")
        later(0.2){self.evaluate("({scroll:scrollY,hint:document.querySelector('#start-hint').textContent,label:document.querySelector('#session').textContent,starts:window.verifyStarts})"){v in
            self.check("Start_budget_validation_inline_no_scroll_or_request",v["scroll"] as? Double==0 && (v["hint"] as? String ?? "").contains("денежные пределы") && v["starts"] as? Int==0 && v["label"] as? String=="Начать",v)
            app.js("window.verifyState={...window.verifyState,configured:true,settings:{...window.verifyState.settings,budget_confirmed:false,spending_mode:'unlimited',unlimited_spend_approved:true}};window.calmStartVerify.setState(window.verifyState);window.calmStartVerify.start();window.calmStartVerify.start();")
            self.later(0.2){self.evaluate("({label:document.querySelector('#session').textContent,spinner:document.querySelector('#session').classList.contains('connecting'),stopEnabled:!document.querySelector('#stop').disabled,starts:window.verifyStarts})"){v in
                self.check("Start_unlimited_real_connecting_label_and_repeat_suppression",v["label"] as? String=="Подключаюсь…" && v["spinner"] as? Bool==true && v["stopEnabled"] as? Bool==true && v["starts"] as? Int==1,v)
                app.js("window.calmStartVerify.stop();")
                self.later(1.2){self.evaluate("({phase:window.calmStartVerify.get(),starts:window.verifyStarts,stops:window.verifyStops})"){v in
                    let phase=v["phase"] as? [String:Any] ?? [:]
                    self.check("Stop_during_connecting_cancels_late_Start_without_restart",v["starts"] as? Int==1 && (v["stops"] as? Int ?? 0)>=2 && phase["connecting"] as? Bool==false && phase["userStopped"] as? Bool==true,v)
                    app.js("window.verifyStartError=true;window.calmStartVerify.setState(window.verifyState);window.calmStartVerify.start();")
                    self.later(0.4){self.evaluate("({hint:document.querySelector('#start-hint').textContent,phase:window.calmStartVerify.get(),starts:window.verifyStarts})"){v in
                        let phase=v["phase"] as? [String:Any] ?? [:]
                        self.check("Start_error_visible_no_automatic_retry",v["hint"] as? String=="Synthetic validation error" && phase["connecting"] as? Bool==false && v["starts"] as? Int==2,v)
                        app.js("window.fetch=window.verifyFetch;delete window.calmStartVerifyState;document.querySelector('#start-hint').textContent='';document.querySelector('#open-start-settings').hidden=true;document.querySelector('#mode').value='replay';document.querySelector('#mode').dispatchEvent(new Event('change'));window.scrollTo(0,0);")
                        self.verifyPersonalContextUI()
                    }}
                }}
            }}
        }}
    }
    func verifyPersonalContextUI(){
        guard let app=owner else{return}
        app.js("document.querySelector('#personal-context').value='Синтетическая община Альфа.';document.querySelector('#save-personal-context').click();")
        later(0.4){self.evaluate("({value:document.querySelector('#personal-context').value,status:document.querySelector('#personal-context-status').textContent,present:window.calmProfilePresent})"){v in
            self.check("local_profile_save_no_model_call",v["value"] as? String=="Синтетическая община Альфа." && (v["status"] as? String ?? "").contains("Сохранено локально"),v)
            app.js("document.querySelector('#personal-context').value='';window.calmProfileVerifyReload();")
            self.later(0.3){self.evaluate("({value:document.querySelector('#personal-context').value})"){v in
                self.check("local_profile_reload_restores_saved_value",v["value"] as? String=="Синтетическая община Альфа.",v)
                app.js("document.querySelector('#personal-context').value='Синтетический профиль Бета.';document.querySelector('#save-personal-context').click();")
                self.later(0.3){self.evaluate("({value:document.querySelector('#personal-context').value,status:document.querySelector('#personal-context-status').textContent})"){v in
                    self.check("local_profile_edit_saved",v["value"] as? String=="Синтетический профиль Бета." && (v["status"] as? String ?? "").contains("Сохранено локально"),v)
                    app.js("document.querySelector('#clear-personal-context').click();")
                    self.later(0.3){self.evaluate("({value:document.querySelector('#personal-context').value,status:document.querySelector('#personal-context-status').textContent,present:window.calmProfilePresent})"){v in
                        self.check("local_profile_clear_restores_empty_behavior",v["value"] as? String=="" && v["present"] as? Bool==false && (v["status"] as? String ?? "").contains("очищен"),v)
                        app.js("document.querySelector('#unlimited-spend').checked=true;document.querySelector('#unlimited-spend').dispatchEvent(new Event('input'));")
                        self.evaluate("({plan:document.querySelector('#text-budget-plan').textContent})"){v in
                            self.check("unlimited_UI_marks_paid_usage_without_money_caps",(v["plan"] as? String ?? "").contains("Без денежных пределов") && (v["plan"] as? String ?? "").contains("платные"),v)
                            app.js("document.querySelector('#unlimited-spend').checked=false;document.querySelector('#unlimited-spend').dispatchEvent(new Event('input'));")
                            self.evaluate("({plan:document.querySelector('#text-budget-plan').textContent})"){v in
                                self.check("limited_UI_restores_budget_plan_without_save_or_spend",!(v["plan"] as? String ?? "").contains("Без денежных пределов"),v)
                                self.verifyQuotedBoundary()
                            }
                        }
                    }}
                }}
            }}
        }}
    }
    func verifyQuotedBoundary(){
        guard let app=owner else{finish(false);return}
        app.js("Promise.all([import('/t9.js'),import('/state.js')]).then(([a,b])=>{const l=new a.ConversationLedger(),t=new b.Transcript();let n=0;for(const text of ['Всё: «Ты меня слыш','ишь','?»']){l.observe(text,++n*100);t.add({kind:'delta',seq:n,text});}window.calmQuotedProof={revision:l.revision,stabilization:l.stabilization,latest:l.items.at(-1)?.text,history:t.history.join(''),draft:t.draft,spoken:l.replyContext()?.own_response_state.spoken};});")
        later(0.3){self.evaluate("window.calmQuotedProof||{}"){v in
            self.check("quoted_provider_question_commits_in_native_WK_without_silence",v["revision"] as? Int==1 && v["stabilization"] as? Int==600 && v["latest"] as? String=="Всё: «Ты меня слышишь?»" && v["history"] as? String=="Всё: «Ты меня слышишь?»" && v["draft"] as? String=="" && v["spoken"] as? String=="unknown",v)
            self.verifyManualChoiceUX()
        }}
    }
    // Recorded public model pairs were validated by the final offline guard before injection.
    // This checks real WK presentation, not fresh model generation or transport.
    func verifyManualChoiceUX(){
        guard let app=owner else{finish(false);return}
        app.js("window.choiceContextBefore=JSON.stringify(window.calmReplyContext?.());window.calmT9InjectBatch([{en:'Yes, I can hear you clearly.',ru:'Да, я вас хорошо слышу.',kind:'positive'},{en:'The sound is breaking up.',ru:'Звук прерывается.',kind:'negative'},{en:'Could you repeat that?',ru:'Можете повторить?',kind:'clarify'}]);")
        evaluate("({kind:document.querySelector('#reply-choice-kind').textContent,options:[...document.querySelectorAll('#focus-options .choice-label')].map(e=>e.textContent),english:document.querySelector('#english').value,open:document.querySelector('#alternatives').open,note:document.querySelector('.choice-note').textContent})"){v in
            self.check("manual_position_types_visible_unselected",(v["kind"] as? String ?? "").contains("Да / подходит") && v["options"] as? [String]==["Да / подходит","Нет / не подходит","Уточнить"] && v["english"] as? String=="" && v["open"] as? Bool==true && (v["note"] as? String ?? "").contains("Выберите то, что верно для вас"),v)
            app.js("document.querySelectorAll('#focus-options button')[1].click();")
            self.evaluate("({english:document.querySelector('#english').value,kind:document.querySelector('#reply-choice-kind').textContent})"){v in
                self.check("manual_negative_position_selects_only_by_click",v["english"] as? String=="The sound is breaking up." && (v["kind"] as? String ?? "").contains("Вы выбрали: Нет / не подходит"),v)
                app.js("window.calmT9InjectBatch([{en:'That works for me.',ru:'Мне подходит.',kind:'positive'}]);")
                self.evaluate("({english:document.querySelector('#english').value,sameContext:JSON.stringify(window.calmReplyContext?.())===window.choiceContextBefore})"){v in
                    self.check("new_positions_preserve_selected_EN_and_remote_context",v["english"] as? String=="The sound is breaking up." && v["sameContext"] as? Bool==true,v)
                    app.js("document.querySelector('#english').value='';document.querySelector('#english').dispatchEvent(new Event('input'));document.querySelector('#t9-history').replaceChildren();document.querySelector('#reply-lead').blur();document.querySelector('#reply-lead').dispatchEvent(new Event('pointerleave'));")
                    self.verifyRecordedReplyPresentation()
                }
            }
        }
    }
    func verifyRecordedReplyPresentation(_ index:Int=0){
        guard let app=owner else{finish(false);return}
        let groups:[String]=["[{\"en\":\"Please say that again more slowly.\",\"ru\":\"Пожалуйста, повторите это медленнее.\"},{\"en\":\"Can you speak a little louder?\",\"ru\":\"Можете говорить немного громче?\"}]", "[{\"en\":\"Which item or feature are you talking about?\",\"ru\":\"О какой вещи или функции вы говорите?\"}]", "[{\"en\":\"What item or service is this about?\",\"ru\":\"О каком товаре или услуге речь?\"},{\"en\":\"What exactly should delivery cover?\",\"ru\":\"Что именно должна включать доставка?\"}]", "[{\"en\":\"What exact link and error details do you have?\",\"ru\":\"Какая именно ссылка и какие детали ошибки у вас есть?\"},{\"en\":\"Please send the broken URL and what should happen.\",\"ru\":\"Пожалуйста, пришлите неработающую ссылку и что должно происходить.\"},{\"en\":\"Which part of the link needs fixing, and where does it fail?\",\"ru\":\"Какая часть ссылки требует исправления и где она ломается?\"}]"]
        let expected:[String]=["Please say that again more slowly.", "Which item or feature are you talking about?", "What item or service is this about?", "What exact link and error details do you have?"]
        if index>=groups.count {
            app.js("document.querySelector('#reply-lead').click();window.calmT9InjectBatch([{en:'Please explain the next step.',ru:'Объясните следующий шаг.'}]);")
            evaluate("({english:document.querySelector('#english').value})"){v in
                self.check("recorded_real_reply_manual_choice_survives_next_batch",v["english"] as? String==expected.last)
                app.js("document.querySelector('#english').value='';document.querySelector('#english').dispatchEvent(new Event('input'));document.querySelector('#t9-history').replaceChildren();window.calmFocusStale();")
                self.step()
            }
            return
        }
        app.js("document.querySelector('#reply-lead').blur();document.querySelector('#reply-lead').dispatchEvent(new Event('pointerleave'));document.querySelector('#english').value='';document.querySelector('#english').dispatchEvent(new Event('input'));window.calmT9InjectBatch("+groups[index]+");")
        evaluate("({lead:document.querySelector('#reply-lead').textContent,english:document.querySelector('#english').value,disabled:document.querySelector('#reply-lead').disabled})"){v in
            self.check("recorded_real_complete_reply_offer_"+String(index+1),v["lead"] as? String==expected[index] && v["english"] as? String=="" && v["disabled"] as? Bool==false,v)
            self.verifyRecordedReplyPresentation(index+1)
        }
    }
    func step(){
        guard let app=owner else{return}
        if phase==0 {
            phase=10
            evaluate("({paid:document.querySelector('#translate').disabled,visibility:document.visibilityState,focused:document.hasFocus(),font:Number(document.querySelector('#font').value),capture:document.querySelector('#capture-start').disabled,ready:!document.querySelector('#start').disabled})"){[weak self] value in
                guard let self=self else{return}
                app.openCapture();self.check("native_capture_gate_does_not_launch_helper",app.captureChild==nil)
                self.check("paid_and_audio_disabled",value["paid"] as? Bool==true && value["capture"] as? Bool==true)
                self.check("offline_replay_ready",value["ready"] as? Bool==true,value)
                if CommandLine.arguments.contains("--expect-persisted-settings"){self.check("settings_survive_full_process_relaunch",value["font"] as? Int==34)}
                guard value["paid"] as? Bool==true,value["capture"] as? Bool==true,value["ready"] as? Bool==true else{self.finish(false);return}
                app.js("document.querySelector('#session').click();document.querySelector('#session').click();")
                self.later(2.0){
                    app.js("window.calmOfflineBurst(250);")
                    self.awaitAutomaticEmptyIntent(deadline:Date().addingTimeInterval(5))
                }
            }
        } else if phase==1 {
            phase=2
            evaluate("({font:Number(document.querySelector('#font').value),paused:document.querySelector('#reading-state').textContent,paid:document.querySelector('#translate').disabled,rows:document.querySelectorAll('.transcript-row').length})"){[weak self] value in
                guard let self=self else{return}
                self.check("settings_survive_close_reopen",value["font"] as? Int==34 && (value["paused"] as? String ?? "").contains("паузе"),value)
                self.check("paid_still_disabled_after_reopen",value["paid"] as? Bool==true)
                self.check("private_session_content_not_persisted",value["rows"] as? Int==0)
                self.oldChild=app.backend;app.backend?.terminate()
                self.awaitChildFailure(deadline:Date().addingTimeInterval(5))
            }
        } else if phase==2 {
            phase=3
            evaluate("({ready:!document.querySelector('#start').disabled,font:Number(document.querySelector('#font').value),paid:document.querySelector('#translate').disabled})"){[weak self] value in
                guard let self=self else{return}
                self.check("manual_retry_recovers",value["ready"] as? Bool==true && value["font"] as? Int==34 && value["paid"] as? Bool==true,value)
                self.verifyReplyCancel()
            }
        }
    }
    func awaitAutomaticEmptyIntent(deadline:Date){
        evaluate("({batches:document.querySelectorAll('#t9-history .t9-batch').length,intent:document.querySelector('#intent').value,english:document.querySelector('#english').value})"){[weak self] value in
            guard let self=self else{return}
            let appeared=(value["batches"] as? Int ?? 0)>0
            if appeared || Date()>=deadline {
                let passed=appeared && value["intent"] as? String=="" && value["english"] as? String==""
                self.check("automatic_T9_with_empty_intent_no_reply_button",passed,value)
                guard passed else{self.finish(false);return}
                self.verifyCameraLayout()
            } else {self.later(0.2){self.awaitAutomaticEmptyIntent(deadline:deadline)}}
        }
    }
    func verifyCameraLayout(){
        guard let app=owner else{return}
        app.js("document.querySelector('#stop').click();document.querySelector('#mode').value='live';document.querySelector('#mode').dispatchEvent(new Event('change'));")
        later(0.7){self.verifyStoppedCameraLayout()}
    }
    func verifyStoppedCameraLayout(){
        guard let app=owner else{return}
        app.js("document.querySelector('#theme').value='dark';document.querySelector('#theme').dispatchEvent(new Event('change'));document.querySelector('#font').value='38';document.querySelector('#font').dispatchEvent(new Event('input'));document.querySelector('#focus-caption').textContent='Давайте обсудим следующий шаг. Что для вас сейчас важнее всего?';window.calmT9InjectBatch([{en:'Could you explain the next step?',ru:'Можете объяснить следующий шаг?'},{en:'What should we focus on first?',ru:'На чём нам сначала сосредоточиться?'}]);window.scrollTo(0,0);")
        later(0.4){
            self.evaluate("({mode:window.calmMode,modeInput:document.querySelector('#mode').value,phase:window.calmStartVerify.get(),trace:window.calmLatencyMarks.slice(-15),caption:document.querySelector('#focus-caption').getBoundingClientRect().toJSON(),answer:document.querySelector('.answer-hero').getBoundingClientRect().toJSON(),width:innerWidth,height:innerHeight,lead:document.querySelector('#reply-lead').textContent,english:document.querySelector('#english').value,folded:!document.querySelector('#transcript-details').open&&!document.querySelector('#settings').open,theme:getComputedStyle(document.documentElement).getPropertyValue('--bg').trim(),font:parseFloat(getComputedStyle(document.querySelector('#reply-lead')).fontSize),overflow:document.documentElement.scrollWidth>innerWidth})"){v in
                let c=v["caption"] as? [String:Double] ?? [:],a=v["answer"] as? [String:Double] ?? [:],w=v["width"] as? Double ?? 0
                self.check("camera_caption_and_answer_upper_center",(c["top"] ?? 999)<130 && (a["top"] ?? 999)<360 && abs((c["x"] ?? 0)+(c["width"] ?? 0)/2-w/2)<3 && abs((a["x"] ?? 0)+(a["width"] ?? 0)/2-w/2)<3,v)
                self.check("dark_theme_large_text_secondary_folded_no_auto_choice",v["theme"] as? String=="#10151d" && (v["font"] as? Double ?? 0)>=38 && v["folded"] as? Bool==true && v["english"] as? String=="" && v["overflow"] as? Bool==false,v)
                self.cameraSnapshot("CAMERA-DARK.png"){
                    app.js("document.querySelector('#reply-lead').focus();document.querySelector('#reply-lead').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));document.querySelector('#show-meaning').focus();document.querySelector('#show-meaning').dispatchEvent(new KeyboardEvent('keydown',{key:' ',bubbles:true}));")
                    self.evaluate("({chosen:document.querySelector('#english').value,meaning:document.querySelector('#answer-meaning').textContent,visible:!document.querySelector('#answer-meaning').hidden,top:document.querySelector('.answer-hero').getBoundingClientRect().top})"){prior in
                        app.js("window.calmT9InjectBatch([{en:'Which date would suit you?',ru:'Какая дата вам подойдёт?'},{en:'Could you give an example?',ru:'Можете привести пример?'}]);document.querySelector('#theme').value='light';document.querySelector('#theme').dispatchEvent(new Event('change'));")
                        self.evaluate("({chosen:document.querySelector('#english').value,top:document.querySelector('.answer-hero').getBoundingClientRect().top,meaning:document.querySelector('#answer-meaning').textContent,bg:getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()})"){v in
                            self.check("keyboard_select_and_meaning_toggle",prior["chosen"] as? String=="Could you explain the next step?" && prior["visible"] as? Bool==true,prior)
                            self.check("selected_center_answer_and_position_survive_new_group_and_theme",v["chosen"] as? String==prior["chosen"] as? String && v["meaning"] as? String==prior["meaning"] as? String && v["top"] as? Double==prior["top"] as? Double && v["bg"] as? String=="#f5f6f8",v)
                            self.cameraSnapshot("CAMERA-LIGHT.png"){
                                app.window.setContentSize(NSSize(width:560,height:650))
                                self.later(0.3){self.evaluate("({overflow:document.documentElement.scrollWidth>innerWidth,caption:document.querySelector('#focus-caption').getBoundingClientRect().toJSON(),answer:document.querySelector('.answer-hero').getBoundingClientRect().toJSON(),width:innerWidth})"){v in
                                    let a=v["answer"] as? [String:Double] ?? [:],w=v["width"] as? Double ?? 0
                                    self.check("narrow_resize_no_horizontal_overflow_centered_answer",v["overflow"] as? Bool==false && abs((a["x"] ?? 0)+(a["width"] ?? 0)/2-w/2)<3,v)
                                    self.cameraSnapshot("CAMERA-NARROW.png"){
                                        app.window.setContentSize(NSSize(width:1180,height:820))
                                        app.js("document.querySelector('#english').value='';document.querySelector('#answer-meaning').hidden=true;document.querySelector('#show-meaning').setAttribute('aria-expanded','false');")
                                        self.later(0.3){self.verifyFreshSuggestions()}
                                    }
                                }}
                            }
                        }
                    }
                }
            }
        }
    }
    func verifyFreshSuggestions(){
        guard let app=owner else{return}
        app.js("document.querySelector('#reply-lead').blur();document.querySelector('#reply-lead').dispatchEvent(new Event('pointerleave'));window.calmT9InjectBatch([{en:'Could you explain this route?',ru:'Можете объяснить этот маршрут?'},{en:'Which route is safer?',ru:'Какой маршрут безопаснее?'}]);window.calmFocusStale();document.querySelector('#reply-lead').click();")
        self.later(0.2){self.evaluate("({disabled:document.querySelector('#reply-lead').disabled,text:document.querySelector('#reply-lead').textContent,chosen:document.querySelector('#english').value})"){v in
            self.check("obsolete_unselected_main_reply_disabled_without_auto_choice",v["disabled"] as? Bool==true && v["chosen"] as? String=="" && v["text"] as? String=="Жду законченной реплики…",v)
            app.js("window.calmT9InjectBatch([{en:'What should we check first?',ru:'Что проверим сначала?'},{en:'Could you clarify the next step?',ru:'Можете уточнить следующий шаг?'}]);")
            self.evaluate("({disabled:document.querySelector('#reply-lead').disabled,text:document.querySelector('#reply-lead').textContent,chosen:document.querySelector('#english').value})"){v in
                self.check("fresh_main_reply_restores_manual_selection",v["disabled"] as? Bool==false && v["chosen"] as? String=="" && v["text"] as? String=="What should we check first?",v)
                app.js("document.querySelector('#reply-lead').click();window.calmFocusStale();")
                self.evaluate("({chosen:document.querySelector('#english').value})"){v in
                    self.check("chosen_reply_survives_freshness_invalidation",v["chosen"] as? String=="What should we check first?",v)
                    app.js("document.querySelector('#english').value='';")
                    self.later(0.2){self.prepareReading()}
                }
            }
        }}
    }
    func cameraSnapshot(_ name:String,_ next:@escaping()->Void){
        owner?.web?.takeSnapshot(with:WKSnapshotConfiguration()){image,error in
            if let image=image,let tiff=image.tiffRepresentation,let bitmap=NSBitmapImageRep(data:tiff),let png=bitmap.representation(using:.png,properties:[:]){try? png.write(to:self.proof.appendingPathComponent(name));self.check(name,true)}else{self.check(name,false)}
            next()
        }
    }
    func verifyReplyCancel(){
        guard let app=owner else{finish(false);return}
        app.js("document.querySelector('#mock-translate').click();document.querySelector('#cancel-reply').click();")
        later(0.4){[weak self] in
            self?.evaluate("({cancelled:document.querySelector('#reply-status').textContent.includes('отменено'),hidden:document.querySelector('#cancel-reply').hidden})"){[weak self] value in
                guard let self=self else{return}
                self.check("cancel_mock_reply_without_provider_or_retry",value["cancelled"] as? Bool==true && value["hidden"] as? Bool==true,value)
                self.verifyT9AndSettings()
            }
        }
    }
    func verifyT9AndSettings(){
        guard let app=owner else{finish(false);return}
        app.js("document.querySelector('#mode').value='live';document.querySelector('#mode').dispatchEvent(new Event('change'));document.querySelector('#session').click();")
        later(0.5){[weak self] in
            self?.evaluate("({noPopup:!document.querySelector('#consent'),noDuration:!document.querySelector('#session-minutes'),settings:document.querySelector('#settings').open,auto:document.querySelector('#auto-suggestions').checked,ownMicOff:!document.querySelector('#own-mic').checked,reply:document.querySelector('#suggest').textContent})"){[weak self] value in
                guard let self=self else{return}
                self.check("no_start_interstitial_or_duration_picker",value["noPopup"] as? Bool==true && value["noDuration"] as? Bool==true,value)
                self.check("remote_T9_default_and_optional_mic_off",value["auto"] as? Bool==true && value["ownMicOff"] as? Bool==true)
                self.check("separate_reply_and_translate_labels",value["reply"] as? String=="Предложить ответ")
                app.js("document.querySelector('#connection-text').checked=true;document.querySelector('#text-budget').value='0.50';document.querySelector('#text-budget').dispatchEvent(new Event('input'));")
                self.evaluate("({preview:document.querySelector('#text-budget-plan').textContent})"){v in
                    self.check("estimated_budget_preview_explains_size_and_errors",(v["preview"] as? String ?? "").contains("примерно 45") && (v["preview"] as? String ?? "").contains("ошибки и отмены"),v)
                    app.js("document.querySelector('#text-budget').value='2';document.querySelector('#text-budget').dispatchEvent(new Event('input'));")
                    self.evaluate("({preview:document.querySelector('#text-budget-plan').textContent})"){w in
                        self.check("estimated_budget_preview_updates_without_saving_or_spend",(w["preview"] as? String ?? "").contains("примерно 181"),w)
                        app.js("document.querySelector('#text-budget').value='0.50';document.querySelector('#text-budget').dispatchEvent(new Event('input'));")
                    }
                }
                app.js("document.querySelector('#reply-history-details').open=true;document.querySelector('#t9-history').dispatchEvent(new Event('pointerenter'));window.calmT9InjectBatch([{en:'Could you explain the plan?',ru:'Можете объяснить план?'},{en:'What should we clarify first?',ru:'Что нам сначала уточнить?'}]);document.querySelector('#t9-history .t9-option').click();")
                self.evaluate("({first:document.querySelector('#t9-history .t9-option strong')?.textContent,count:document.querySelectorAll('.t9-batch').length,top:document.querySelector('#t9-history').scrollTop,selected:document.querySelector('#english').value})"){previous in
                    app.js("window.calmT9InjectBatch([{en:'Which part matters most?',ru:'Какая часть важнее всего?'},{en:'Could you give an example?',ru:'Можете привести пример?'}],true);")
                    self.evaluate("({first:document.querySelector('#t9-history .t9-option strong')?.textContent,count:document.querySelectorAll('.t9-batch').length,top:document.querySelector('#t9-history').scrollTop,selected:document.querySelector('#english').value})"){value in
                        self.check("T9_immutable_batches_preserve_reading_and_selection",value["first"] as? String==previous["first"] as? String && (value["count"] as? Int ?? 0)>(previous["count"] as? Int ?? 0) && abs((value["top"] as? Double ?? 0)-(previous["top"] as? Double ?? 0))<1 && value["selected"] as? String==previous["selected"] as? String,value)
                        app.js("document.querySelector('#t9-history .t9-option').click();")
                        self.evaluate("({selected:document.querySelector('#english').value,marked:document.querySelector('#t9-history .t9-option').getAttribute('aria-pressed'),stale:document.querySelector('#t9-history .t9-batch:last-child').classList.contains('stale'),stamp:document.querySelector('#t9-history .t9-batch:last-child .stamp').textContent})"){v in
                            self.check("earlier_reply_explicitly_labelled_and_manual_choice_highlighted",v["marked"] as? String=="true" && v["stale"] as? Bool==true && v["selected"] as? String=="Could you explain the plan?",v)
                        }
                        app.js("document.querySelector('#connection-audio').checked=false;document.querySelector('#connection-text').checked=false;document.querySelector('#save-connection').click();")
                        self.later(0.5){self.finish(true)}
                    }
                }
            }
        }
    }
    func awaitChildFailure(deadline:Date){
        guard let app=owner else{finish(false);return}
        let gone=app.backend==nil && app.web==nil && app.window.isVisible
        if gone || Date()>=deadline {
            check("child_failure_visible_without_auto_restart",gone,["backendGone":app.backend==nil,"webGone":app.web==nil,"windowVisible":app.window.isVisible])
            guard gone else{finish(false);return}
            app.retryBackend() // deliberate test action, never automatic product behavior
        } else {later(0.2){[weak self] in self?.awaitChildFailure(deadline:deadline)}}
    }
    func prepareReading(){
        guard let app=owner else{return}
        app.js("document.querySelector('#mode').value='replay';document.querySelector('#mode').dispatchEvent(new Event('change'));document.querySelector('#transcript-details').open=true;document.querySelector('#reply-history-details').open=true;document.querySelector('#thought-editor').open=true;document.querySelector('#stop').click();document.querySelector('#pause-reading').click();document.querySelector('#font').value='32';document.querySelector('#font').dispatchEvent(new Event('input'));document.querySelector('#history').scrollTop=200;document.querySelector('#intent').value='Повторите, пожалуйста, немного медленнее.';document.querySelector('#mock-suggest').click();")
        app.larger() // native menu shortcut handler→actual web input event→UserDefaults
        later(2.2){[weak self] in self?.readAndContinue()}
    }
    func readAndContinue(){
        evaluate("({rows:document.querySelectorAll('.transcript-row').length,top:document.querySelector('#history').scrollTop,font:Number(document.querySelector('#font').value),options:document.querySelectorAll('#options button').length,english:document.querySelector('#english').value,intent:document.querySelector('#intent').value,t9:document.querySelectorAll('#t9-history .t9-batch').length,first:document.querySelector('.transcript-row span')?.textContent})"){[weak self] value in
            guard let self=self,let app=self.owner else{return}
            self.check("offline_rows_accumulate",(value["rows"] as? Int ?? 0)>10,value["rows"] ?? 0)
            self.check("manual_options_not_auto_selected",value["options"] as? Int==2 && value["english"] as? String=="" && value["intent"] as? String=="Повторите, пожалуйста, немного медленнее.")
            self.check("automatic_T9_without_typed_intent_or_click",(value["t9"] as? Int ?? 0)>0,value["t9"] ?? 0)
            self.check("native_font_handler",value["font"] as? Int==34)
            self.anchor=value["top"] as? Double ?? 0
            app.js("document.querySelector('#start').click();")
            self.later(1.2){app.js("window.calmOfflineBurst(200);");self.later(0.1){self.finishReading(value["first"] as? String ?? "",value["rows"] as? Int ?? 0)}}
        }
    }
    func finishReading(_ first:String,_ rows:Int){
        evaluate("({rows:document.querySelectorAll('.transcript-row').length,top:document.querySelector('#history').scrollTop,first:document.querySelector('.transcript-row span')?.textContent})"){[weak self] value in
            guard let self=self,let app=self.owner else{return}
            self.check("reading_anchor_preserved_while_accumulating",self.anchor>0 && abs((value["top"] as? Double ?? -100)-self.anchor)<1 && (value["rows"] as? Int ?? 0)>rows,value)
            self.check("committed_text_unchanged",value["first"] as? String==first)
            app.js("document.querySelector('#stop').click();document.querySelector('#options button').click();document.querySelector('#english').value='Could you repeat that a little more slowly, please?';")
            self.later(0.3){
                self.evaluate("({english:document.querySelector('#english').value,intent:document.querySelector('#intent').value})"){value in
                    self.check("reply_manually_selected_and_edited",value["english"] as? String=="Could you repeat that a little more slowly, please?" && value["intent"] as? String=="Повторите, пожалуйста, немного медленнее.",value)
                    app.js("window.calmT9InjectBatch([{en:'Where should we meet?',ru:'Где встретимся?'}]);")
                    self.later(0.1){
                        self.evaluate("({count:document.querySelectorAll('#t9-history .t9-batch:last-child .t9-option').length,english:document.querySelector('#english').value})"){v in
                            self.check("single_validated_option_keeps_manual_choice",v["count"] as? Int==1 && v["english"] as? String=="Could you repeat that a little more slowly, please?",v)
                            self.snapshotAndClose()
                        }
                    }
                }
            }
        }
    }
    func snapshotAndClose(){
        guard let app=owner,let view=app.web else{finish(false);return}
        view.takeSnapshot(with:WKSnapshotConfiguration()){[weak self] image,error in
            guard let self=self else{return}
            if let image=image,let tiff=image.tiffRepresentation,let bitmap=NSBitmapImageRep(data:tiff),let png=bitmap.representation(using:.png,properties:[:]) {
                try? png.write(to:self.proof.appendingPathComponent("APP-WINDOW.png"))
                self.check("live_webview_snapshot",true)
            } else {self.check("live_webview_snapshot",false,"Snapshot unavailable")}
            self.oldChild=app.backend
            app.window.performClose(nil)
            self.later(1.2){
                self.check("close_stops_own_backend",self.oldChild?.isRunning != true && app.backend==nil && !app.window.isVisible)
                self.check("settings_saved_to_userdefaults",app.defaults.dictionary(forKey:"reading")?["font"] as? Int==34)
                self.phase=1;app.reopen()
            }
        }
    }
    func finish(_ success:Bool){
        let passed=success && !checks.contains(where:{$0["passed"] as? Bool != true})
        let result:[String:Any]=["passed":passed,"kind":"live_native_window_and_mock_offline_UI_with_deterministic_synthetic_bursts","checks":checks,"audio_playback":false,"capture":false,"provider_calls":0,"keychain_reads":0]
        if let data=try? JSONSerialization.data(withJSONObject:result,options:[.prettyPrinted,.sortedKeys]){try? data.write(to:proof.appendingPathComponent("LIFECYCLE-RESULT.json"))}
        owner?.stopBackend()
        DispatchQueue.main.async{NSApp.terminate(nil)}
    }
}
