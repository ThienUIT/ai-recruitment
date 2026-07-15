# Talent Intelligence permissions

The extension reuses the authenticated Dify console session, current tenant resolution, and existing workspace roles. It creates no role tables or independent tokens.

| Action | Dify permission |
| --- | --- |
| View/list candidates and jobs | Any authenticated member of the current workspace |
| Create/update candidates and jobs; request deletion | `Account.has_edit_permission` (owner, admin, editor) |
| Create/activate scoring policies | `Account.is_admin_or_owner` |
| List or verify audit events | `Account.is_admin_or_owner` |

```mermaid
flowchart LR
    Controller --> Login[Dify login_required]
    Login --> Context[current_account_with_tenant]
    Context --> Permission[TalentAction mapping]
    Permission --> Service
    Service --> Repository
```

Permission checks are centralized in `permissions/mapping.py`. Tenant isolation is separate and mandatory in every repository lookup. Cross-tenant identifiers return HTTP 404, not 403, so object existence is not disclosed.
