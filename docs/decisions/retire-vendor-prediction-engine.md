# Retire the vendor prediction engine

## What was removed

`AIRecommendationEngine` (`app/modules/ai_chat/services/ai_recommendation_engine.py`)
and its two re-export lines, in `app/modules/ai_chat/services/ai_analysis_service.py`
and `app/modules/ai_chat/services/__init__.py`.

## Why

The engine's vendor performance "prediction" was fixed arithmetic presented as a
forecast, not a model output. Nothing in the codebase constructed the class, so it
was unreachable from any route, job or CLI command.

## Evidence

```
grep -rn "AIRecommendationEngine\|ai_recommendation_engine" app tests scripts manage.py docs
```

returned only:

- the module itself (`app/modules/ai_chat/services/ai_recommendation_engine.py`)
- the re-export in `app/modules/ai_chat/services/ai_analysis_service.py`
- the re-export in `app/modules/ai_chat/services/__init__.py`
- the docstring line listing the engine in `ai_analysis_service.py`

No route, service, job, CLI command or test constructed or imported the class.

## Successor

Vendor performance forecasting is planned as its own service in Release 3
(story TB-0117, the forecasting service). That work is not blocked by this
removal: the engine was never wired to anything, so nothing needs to be
repointed before the successor lands.

## Reversible variant

The removed file can be restored from git history
(`git show <commit>^:app/modules/ai_chat/services/ai_recommendation_engine.py`)
if a future need for its logic emerges before the forecasting service ships.
