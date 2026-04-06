# STATE_MEMORY — state & memory (AgentOps Triage PoC)

## 1) Что такое state в PoC
State — детерминированные данные о ходе сессии:
- инцидент, шаги, результаты tool-calls (sanitized), принятые решения, итоговый отчёт.

## 2) Что такое memory в PoC
Memory — сжатое представление контекста для LLM и продолжения диалога:
- rolling summary (обновляется каждые N шагов),
- “known facts” (короткий список подтверждённых наблюдений),
- ограничения: не хранить raw PII и длинные логи.

## 3) Политика summarization
Триггеры:
- каждые `N=3` шага,
- или если контекст > `max_context_chars`,
- или перед финальным отчётом.

Выход summary:

### Формат rolling summary
Rolling summary хранится в компактном structured виде:
- `what_we_know`: подтверждённые факты и наблюдения;
- `what_we_tried`: уже выполненные шаги и результаты;
- `open_questions`: чего не хватает для уверенного вывода;
- `current_hypotheses`: 1–3 актуальные hypotheses с кратким статусом.

### Формат known facts
Known facts — это короткий список атомарных подтверждённых утверждений, например:
- `payments-api error_rate increased from 0.8% to 12.4%`
- `logs contain PaymentProviderTimeout after deploy`
- `runbook suggests dependency health check before rollback`

Known facts должны быть:
- grounded;
- краткими;
- без raw PII;
- пригодными для прямого включения в prompt context.

### Eviction и prompt construction
Memory не является бесконечной:
- при росте контекста старые detailed observations сворачиваются в summary;
- в prompt попадают только normalized incident input, rolling summary, known facts, top observations и relevant refs;
- длинные raw logs и retrieval chunks не включаются в prompt целиком;
- eviction происходит в пользу кратких grounded summaries, а не в пользу накопления сырого текста.

В текущем PoC memory носит episodic session-scoped характер и не предназначена для долгосрочного межсессионного reuse.

## 4) Memory safety
- summary проходит через PII redaction
- не включаем инструкции из логов/KB (“не доверяем данным”)