# Dify core modifications

This register tracks changes outside feature-owned Talent Intelligence paths.

| File | Reason and delegation | Conflict risk | Retest |
| --- | --- | --- | --- |
| `api/configs/feature/__init__.py` | Composes the feature-owned configuration into `DifyConfig`; contains no domain behavior. | Low: the mix-in list changes upstream. | Talent Intelligence config unit test and API configuration import. |
| `api/controllers/console/__init__.py` | Calls the feature-owned console registrar. The registrar owns the flag check and route implementation. | Medium: the upstream controller import/registration list changes frequently. | Enabled/disabled health registration tests and authenticated HTTP smoke test. |
| `api/tests/unit_tests/configs/test_dify_config.py` | Verifies disabled default and environment opt-in. | Low. | Run the focused pytest test. |
| `docker/.env.example` | Documents the disabled deployment default. | Low: environment template changes frequently. | Render Compose config with the example copied to `.env`. |

No generic service, model, workflow, authentication, or frontend file is modified through Phase 0.5. The generic console change is a two-line import and delegation hook; all registration behavior remains in `api/extensions/talent_intelligence`.
