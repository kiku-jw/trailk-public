// Prerequisites are reported inline. This never grants consent or changes budgets.
export function startPrerequisite(state){
 if(!state)return {message:'Локальный сервер пока недоступен.',target:'save-connection'};
 const s=state.settings||{};
 if(!s.budget_confirmed&&!(s.spending_mode==='unlimited'&&s.unlimited_spend_approved===true))return {message:'Подтвердите денежные пределы обычной сессии. Тестовый бюджет их не заменяет.',target:'text-budget'};
 if(!s.capture_allowed||!s.cloud_allowed)return {message:'В настройках подключения не сохранён источник звука Zoom → OpenAI.',target:'connection-audio'};
 if(!state.configured)return {message:'Проверьте сохранённое подключение и денежные пределы.',target:'save-connection'};
 return null;
}
