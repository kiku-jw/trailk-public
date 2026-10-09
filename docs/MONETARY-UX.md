# Current approved estimated reserve — 4 October 2026, 08:21 UTC

Production OpenAI text requests use `estimated_v1`; historical ledgers are not migrated. The legacy fixed policy remains for backwards-compatible adapter behavior. Every fresh installation still requires explicit in-app source, cloud and spending consent.

`src/text_budget.py` counts the complete UTF-8 serialized request: instructions, selected data, schema and envelope. It caps that wire body at 8192 bytes, uses its bytes as an intentionally conservative token proxy plus 512 framing tokens, and caps the entire output at 512 tokens. Reserve = ceil-to-microdollar((proxy × $0.75 + output_cap × $4.50)/1M × 1.25). Rates are uncached, verified against [OpenAI's model documentation](https://developers.openai.com/api/docs/models/gpt-5.4-mini) on 2026-10-04. This snapshot blocks after 2026-11-04, unknown provider/model, unknown policy or incompatible output cap. No counting API/admin credential is used.

This is **an estimate with margin, not an exact token count or guaranteed invoice ceiling**: provider framing/billing may differ. Maximum estimated reserve is $0.01104; actual requests vary with full request size. $0.50 supports about 45 maximum-size attempts, $2 about 181; shorter contexts need less reserve. Neither is an hour-long guarantee. The ledger reserves before Keychain/network and retains reservations on failure, cancellation, schema rejection and unknown usage. Returned usage is displayed separately and never releases reserve. Historical fixed reserves are not migrated or refunded.

All paid comparison tests preceded this change and kept their $0.05 attempt reservations. No paid verification of the new estimate was run. Code/UI tests cover Unicode/full schema size, unknown/expired price, oversized input/output cap, insufficient remaining budget before secret access, errors/no retry, and exact preservation of old sums. Below is the prior audit, retained as historical rationale; its statement that fixed $0.05 is current is superseded by this section.

---

# Trailk: аудит денежного интерфейса

В 1.2.2 изменено только отображение. Настройки прямо показывают: $0.50 допускает 10 текстовых попыток, $2 — 40, включая ошибки и отмены. Это не срок работы T9. Во время сессии отдельно показаны резерв попыток, оставшееся число, оценка текста по токенам, неизвестное фактическое списание и наличие выполняющегося запроса. Уменьшение оценки не увеличивает остаток попыток. Исторические ledger и расходный guard остаются без изменений.

## Почему завершённый usage не освобождает остаток

OpenAI рекомендует рассчитывать стоимость входа по `response.usage` и цене модели: это подходит для отображаемой оценки. В уже полученных ответах Trailk есть input/output/cached token counts; долларового подтверждения списания нет. [Официальное описание prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching).

Отдельный [Costs API](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs) возвращает расходы в временных корзинах с группировкой. Это не cost receipt на отдельный response_id. Доступ относится к [Administration](https://developers.openai.com/api/reference/administration/overview); Trailk не подключает admin credentials и не запрашивает дополнительных полномочий.

Вывод аудита: имеющихся response token counts недостаточно для заявления «фактически списано» или безопасного возврата $0.05 исторической попытки. Текущий ledger необратимо резервирует попытку до Keychain/network и не имеет settlement/release. Оценки $0.0006–0.0008 за ответ не превращаются в доказательство отсутствия списания. Никаких новых платных вызовов, возвратов или повышения предела нет.

## Малое предложение для будущего ledger

В новой схеме следует хранить неизменяемый attempt_id и четыре состояния, не мигрируя/переписывая старые суммы:

| Состояние | Основание | Финансовое действие |
| --- | --- | --- |
| pending_reservation | Запрос зарезервирован перед сетью | Полный верхний резерв остаётся удержан |
| completed_usage_estimate | Ответ вернул валидные token counts | Записать токены и оценку отдельно; не назвать её фактическим списанием, резерв не освобождать |
| unknown_charge | Ошибка, отмена, пропавший/невалидный usage | Сохранить полный резерв; повтор автоматически не разрешать |
| confirmed_cost | Только однозначное подтверждение стоимости именно этой попытки | Идемпотентно зачесть подтверждённую стоимость; освобождение разницы возможно только после отдельно проверенного источника подтверждения |

Сообщения о завершении/ошибке после отмены не меняют состояния других attempt_id; повторная settlement одного id не может дважды освобождать резерв. Неизвестную charge нельзя делать нулевой по таймауту. При падении процесса pending становится unknown_charge, а не автоматически бесплатным.

Сейчас нет проверенного request-level источника `confirmed_cost`, поэтому этот settlement не включён. Следующий практичный путь: отдельное финансовое решение для будущих сессий — либо явно разрешённый учёт по token-price estimate с запасом, либо меньший заранее доказанный верхний резерв на ограниченный reply payload. Это меняет политику расходов и требует отдельного решения, не скрытой замены текущего guard.

## Проверки и готовность

21 JS-тест прошёл, включая $0.50→10, $2→40, точность остатка .30−.25→1, исчерпание .10−.10→0, отсутствие пополнения от меньшей оценки, отметку неизвестного списания, запрет недопустимого preview, неизменность исходного state. Python и native UI проверены при выпуске, точные числа — в результате установки.

Historical account balances, spending authorizations and request-cost details are omitted from the public snapshot. Earlier test observations are historical; no live provider verification is claimed by this publication.


## 4 октября: исследование меньшего верхнего резерва

Historical account balances, spending authorizations and request-cost details are omitted from the public snapshot. Earlier test observations are historical; no live provider verification is claimed by this publication.

### Что подтверждено

Фиксированный маршрут: OpenAI `/v1/responses`, snapshot `gpt-5.4-mini-2026-03-17`, без tools, previous_response_id, conversation, файлов/картинок и routing. Собственная мысль ограничена 3000 Python Unicode-символами; выбранный контекст — 6000, reply-контекст — 2400. Эти ограничения не являются границей полного количества billable input tokens: instructions, роли/границы сообщения и JSON schema также участвуют. Проверка крайних Unicode-входов и отказов при 3001/2401/6001 символах проведена offline, без store/network.

[Официальная цена модели](https://developers.openai.com/api/docs/models/gpt-5.4-mini): uncached input $0.75/1M, output $4.50/1M. Cached скидка в верхней границе не используется. Текущий max_output_tokens=1024 ограничивает **все** generated tokens, включая reasoning и невидимое форматирование; effort=none не служит самостоятельным доказательством нулевого reasoning. Это прямо описано в [reasoning guide](https://developers.openai.com/api/docs/guides/reasoning). Таким образом верхняя стоимость выхода по текущему тарифу — $0.004608. Нужны ещё полная входная граница и известные дополнительные сборы.

[Token-counting guide](https://developers.openai.com/api/docs/guides/token-counting) подтверждает: локальные tokenizer/byte calculations не учитывают всю структуру; schemas сложны для локального подсчёта. Endpoint `/v1/responses/input_tokens` возвращает полный точный count до генерации. Официальная [SDK schema](https://github.com/openai/openai-python/blob/main/src/openai/types/responses/input_token_count_params.py) включает instructions, input, reasoning и text.format JSON schema. Cookbook предупреждает, что локальный message-count — оценка, а не постоянная гарантия. Добавить произвольные 1000 токенов или 25% к локальному подсчёту недостаточно для доказательства неизвестного структурного overhead.

### Условно доказуемый будущий путь; НЕ активирован

Нужен preflight точного фиксированного payload, затем резерв **до** генерации. Полный payload должен быть заморожен между count и create: тот же model, instructions, input, reasoning, schema; tools/conversation/previous response/неизвестные поля запрещены. Count-error, неизвестная/просроченная цена, смена маршрута, невалидный count, переполнение или исчерпание денег должны завершать попытку без generation и без retry. Для собственной мысли нужна собственная проверка полного запроса; короткий T9 нельзя использовать как финансовую границу длинной мысли.

Пример условного envelope для T9: официальный полный count ≤2048; max_output_tokens=512 (включая reasoning); uncached цена выше. База `(2048*0.75 + 512*4.50)/1e6 = $0.00384`, с 25% финансовым запасом $0.0048. Это **верхняя граница только при выполненных предпосылках**, не средний usage. $2 тогда хватило бы на 416 попыток, в том числе на 300 запросов за час при минимальном интервале 12 секунд ($1.44 резерва). $0.50 — на 104. Уменьшение output может повысить число incomplete; качество/пригодность 512-токенного ответа не проверены живым прогоном.

Оставшийся конкретный ограничитель: изученные официальные guide/pricing/SDK не установили цену самого count-вызова. Нельзя объявить его бесплатным, передать контекст для нового неоценённого вызова до финансового guard или уменьшить резерв генерации по непроверенному wire-контракту. Endpoint в рамках этого задания не вызывался. Поэтому формула выше не внедрена в активный маршрут и preview честно остаётся 10/40 попыток. Offline mocks не устраняют этот внешний пробел.

Без новых API-вызовов безопасная функциональная альтернатива — сохранять текущие 2–3 варианта дольше и уменьшать частоту обновления: не чаще одного запроса в 90 секунд означало бы не более 40 попыток за час при $2, без ручной кнопки. Это хуже реакции на каждую реплику, а не эквивалент часового естественного T9, и в этом аудите не включено. Предпочтительное продолжение — установить стоимость count preflight и проверить его полный контракт на публичном входе при отдельном разрешённом бюджете; только затем включать меньший irreversible верхний резерв. Новый денежный предел или возврат старых резервов для этого не предлагается.


## Уточнение одинакового стандарта доказательства

Текущие $0.05 **тоже не имеют доказательства абсолютной верхней границы счёта**. В исходном TextAdapter и первоначальном коммите это literal default Ledger.reserve/available, без рассчитанной полной token-bound или ссылки на provider overhead. Доказано только приложение: перед key/network необратимо удерживается $0.05, поэтому разрешённое число попыток не превышается, включая ошибки/отмены. Это большой практический запас для коротких наблюдавшихся ответов, а не доказанная граница invoice. Предыдущую формулировку «верхний резерв» применительно к старому guard следует читать с этим исправлением.

Убрать schema технически можно: сохранить JSON-инструкцию в plain-text ответе и нынешнюю локальную validate_result; либо использовать json_object без schema. Ошибку JSON/формата показывать без retry. Документация Structured Outputs прямо различает JSON validity и schema adherence. Plain text устраняет schema expansion, а строгий лимит UTF-8 всех текстовых полей (instructions + сериализованный input/история + форматная инструкция) ограничивает подконтрольный приложению вход. Однако точный Responses framing для этого snapshot не документирован; пример cookbook 3 tokens/message относится к перечисленным старым Chat Completions моделям и сам обозначен как estimate, не guarantee. Переносить его сюда нельзя. Byte/BPE-bound для своего текста и произвольная надбавка не доказывают полный server input.

Официального подтверждения отдельной тарификации или бесплатности input_tokens/count в проверенных guide/pricing/SDK не найдено. Следовательно не утверждается ни «count платный», ни «count бесплатный». Дополнительную генерацию для проверки endpoint не выполняли.

Продуктовый вариант на решение пользователя: **оценочный бюджет с запасом, не жёсткий лимит счёта OpenAI**. Для будущего ограниченного plain-text T9 можно считать до отправки стоимость полного byte-bound текста + явно помеченную *оценку* framing + максимум всех output tokens, брать uncached текущую цену и запас; неизвестная цена блокирует отправку, старые резервы не пересчитываются, ошибки удерживают новую сумму, никаких retries. Это может убрать практический предел 40, но invoice всё ещё может превысить отображаемый бюджет из-за неизвестного overhead, тарифных/налоговых сборов или отклонения предпосылок. Удаление schema повышает риск непригодных JSON-ответов; меньший output cap повышает incomplete. Точный framing либо точный API-count с известной ценой остаётся условием *строгой* модели. Пользователь может выбрать оценочную модель осознанно; без такого решения guard, источник, лимиты, cadence и установленное приложение не менялись.
