# AgentOps Triage PoC
**Агентная система для триажа инцидентов с инструментами (метрики/логи), базой знаний (runbooks), сессионной памятью, safety-гейтом и evals/observability.**

[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](#)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)](#)
[![CI](https://img.shields.io/badge/ci-github_actions-black.svg?logo=githubactions&logoColor=white)](#)
[![Status](https://img.shields.io/badge/status-PoC-orange.svg)](#)

> Цель PoC: ускорить первичный триаж (MTTA/MTTR) и снизить риск ошибок за счёт контролируемого tool-use, ссылок на источники и safety-слоя.

---

## Возможности
- **Планирование и triage-цикл**: plan → tool → observe → decide
- **Инструменты (read-only)**: метрики и логи (mock/fixtures, далее — реальные интеграции)
- **База знаний**: поиск runbooks/FAQ (простая KB или RAG)
- **State & Memory**: история шагов, summary, повторное использование фактов в рамках сессии
- **Safety**:
  - редактирование/маскирование PII до логирования и до ответа
  - политика инструментов (allowlist/denylist)
  - approval для потенциально опасных действий
- **Observability**: structured logs + метрики + трейсинг шагов агента
- **Evals**: набор тест-кейсов и рубрика качества (accuracy/plan-quality/safety)
