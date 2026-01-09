# Standards Registry

The canonical standards registry is stored in `coordination.db` and seeded via
migrations. Use the CLI to query it:

```bash
motus standards registry
motus standards show STD-REL-001
```

Manual checklists should reference these standards rather than redefining them.
To add or change standards, update the registry data and let the DB versioning
capture the change history.
