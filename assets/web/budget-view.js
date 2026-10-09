// Read-only presentation: these functions never reserve, release or authorize spend.
export const TEXT_ATTEMPT_RESERVE=.05; // Historical fixed reservations only.
export const MAX_ESTIMATED_RESERVE=.01104;
export function canShowExhaustion(state,inflight,stopped){return !!(state?.running&&state.text_budget_exhausted&&!inflight&&!stopped);}
export function attemptCapacity(limit,reserved=0,amount=TEXT_ATTEMPT_RESERVE){
 if(!Number.isFinite(limit)||!Number.isFinite(reserved)||limit<0||reserved<0)return null;
 return Math.max(0,Math.floor((limit-reserved+1e-9)/amount));
}
export function budgetPlan(limit,enabled=true,profileEnabled=false){
 const count=attemptCapacity(limit,0,profileEnabled ? .01872 : MAX_ESTIMATED_RESERVE);
 if(!enabled)return 'Подсказки выключены. Их резерв не используется.';
 if(count===null||limit<.05||limit>2)return 'Укажите предел подсказок от $0.05 до $2.';
 return `Оценочный бюджет: $${limit.toFixed(2)}. Для максимального запроса — примерно ${count} попыток; короткий контекст требует меньше запаса. Резерв считается до отправки, включая ошибки и отмены. Это оценка с запасом, не гарантированный предел счёта и не обещанная длительность.`;
}
export function budgetStatus(state){
 if(state.settings?.spending_mode==='unlimited'&&state.settings?.unlimited_spend_approved)return `Без денежных пределов. Оценочный резерв текста $${(state.text_reserved_usd||0).toFixed(2)}; оценка usage $${(state.estimated_text_usd||0).toFixed(4)}. Stop и технические защиты действуют; фактический счёт у OpenAI.`;
 const limit=state.settings?.text_budget_usd,reserved=state.text_reserved_usd,policy=state.text_budget_policy,count=attemptCapacity(limit,reserved,policy?.kind==='estimated_v1'?policy.maximum_reservation_usd:TEXT_ATTEMPT_RESERVE);
 const estimate=state.estimated_text_usd;
 const held=Number.isFinite(reserved)&&reserved>=0?`$${reserved.toFixed(2)}`:'неизвестен';
 const usage=Number.isFinite(estimate)&&estimate>=0?`$${estimate.toFixed(4)}`:'неизвестна';
 if(policy?.kind==='estimated_v1')return `Оценочный резерв: ${held}; для максимального запроса ещё примерно ${count===null?'неизвестно':count} попыток. Оценка текста по usage: ${usage}; это не гарантированный предел счёта, фактическое списание неизвестно.${state.text_busy?' Один запрос выполняется.':''}`;
 return `Резерв попыток: ${held}; осталось ${count===null?'неизвестно':count}. Оценка текста по токенам: ${usage}; фактическое списание неизвестно.${state.text_busy?' Один запрос выполняется.':''}`;
}
