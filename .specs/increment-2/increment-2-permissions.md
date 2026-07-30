# Increment 2 — Permissions Schema

## Convention
`<domain>:<action>` where action = `create`, `read`, `update`, `delete`, `assign`, `transition`, `verify`.

## Permission Definitions

| Permission Code | Description |
|----------------|-------------|
| `alert:read` | View alerts |
| `alert:read_assigned` | View own assigned alerts |
| `alert:acknowledge` | Acknowledge alert |
| `alert:dismiss` | Dismiss alert |
| `alert:escalate` | Escalate alert to case |
| `alert:configure` | Create/edit alert rules |
| `investigation:create` | Create investigation |
| `investigation:read` | View any investigation |
| `investigation:read_own` | View own investigations |
| `investigation:update` | Edit investigation (findings, conclusion) |
| `investigation:delete` | Delete/destroy investigation |
| `investigation:archive` | Archive investigation |
| `investigation:assign` | Reassign investigation |
| `investigation:transition` | Change status (draft→active→completed) |
| `case:create` | Create compliance case |
| `case:read` | View any case |
| `case:read_assigned` | View assigned cases |
| `case:update` | Edit case details |
| `case:transition` | Change case status |
| `case:escalate` | Escalate case |
| `case:close` | Close case |
| `case:assign` | Reassign case |
| `case:delete` | Delete case |
| `case:decision` | Record decision on case |
| `evidence:create` | Upload evidence |
| `evidence:read` | View evidence |
| `evidence:delete` | Delete evidence |
| `remediation:create` | Create remediation action |
| `remediation:read` | View remediation actions |
| `remediation:update` | Edit remediation action |
| `remediation:delete` | Delete remediation action |
| `remediation:verify` | Verify remediation completion |
| `watchlist:create` | Create watchlist |
| `watchlist:read` | View watchlists |
| `watchlist:update` | Edit watchlist |
| `watchlist:delete` | Delete watchlist |
| `watchlist:add_item` | Add item to watchlist |
| `watchlist:remove_item` | Remove item from watchlist |
| `saved_analysis:create` | Create saved analysis |
| `saved_analysis:read` | View any saved analysis |
| `saved_analysis:read_own` | View own saved analyses |
| `saved_analysis:update` | Edit saved analysis |
| `saved_analysis:delete` | Delete saved analysis |
| `saved_analysis:share` | Share saved analysis |
| `saved_analysis:schedule` | Set schedule on analysis |
| `task:create` | Create task |
| `task:read` | View any task |
| `task:read_assigned` | View assigned tasks |
| `task:update` | Edit task |
| `task:transition` | Change task status |
| `task:assign` | Reassign task |
| `task:verify` | Verify task completion |
| `task:delete` | Delete task |
| `notification:read` | View notifications |
| `notification:update` | Mark read/unread |
| `comment:create` | Add comment |
| `comment:read` | View comments |
| `comment:delete` | Delete any comment |
| `timeline:read` | View activity timeline |

## Role → Permission Mapping

| Permission | Analyst | Compliance | Admin |
|-----------|---------|-----------|-------|
| `alert:read_assigned` | ✓ | ✓ | — |
| `alert:read` | — | — | ✓ |
| `alert:acknowledge` | ✓ | ✓ | ✓ |
| `alert:dismiss` | ✓ | — | ✓ |
| `alert:escalate` | ✓ | ✓ | ✓ |
| `alert:configure` | — | — | ✓ |
| `investigation:create` | ✓ | — | ✓ |
| `investigation:read_own` | ✓ | — | — |
| `investigation:read` | — | ✓ (linked to case) | ✓ |
| `investigation:update` | ✓ | — | ✓ |
| `investigation:delete` | — | — | ✓ |
| `investigation:archive` | ✓ | — | ✓ |
| `investigation:assign` | — | — | ✓ |
| `investigation:transition` | ✓ | — | ✓ |
| `case:create` | — | ✓ | ✓ |
| `case:read_assigned` | ✓ | ✓ | — |
| `case:read` | — | — | ✓ |
| `case:update` | — | ✓ | ✓ |
| `case:transition` | — | ✓ | ✓ |
| `case:escalate` | ✓ | ✓ | ✓ |
| `case:close` | — | ✓ | ✓ |
| `case:assign` | — | — | ✓ |
| `case:delete` | — | — | ✓ |
| `case:decision` | — | ✓ | ✓ |
| `evidence:create` | ✓ | ✓ | ✓ |
| `evidence:read` | ✓ | ✓ | ✓ |
| `evidence:delete` | — | — | ✓ |
| `remediation:create` | — | ✓ | ✓ |
| `remediation:read` | — | ✓ | ✓ |
| `remediation:update` | — | ✓ | ✓ |
| `remediation:delete` | — | — | ✓ |
| `remediation:verify` | — | ✓ | ✓ |
| `watchlist:create` | — | ✓ | ✓ |
| `watchlist:read` | ✓ | ✓ | ✓ |
| `watchlist:update` | — | ✓ | ✓ |
| `watchlist:delete` | — | — | ✓ |
| `watchlist:add_item` | — | ✓ | ✓ |
| `watchlist:remove_item` | — | ✓ | ✓ |
| `saved_analysis:create` | ✓ | — | ✓ |
| `saved_analysis:read_own` | ✓ | — | — |
| `saved_analysis:read` | — | — | ✓ |
| `saved_analysis:update` | ✓ | — | ✓ |
| `saved_analysis:delete` | ✓ | — | ✓ |
| `saved_analysis:share` | ✓ | — | ✓ |
| `saved_analysis:schedule` | ✓ | — | ✓ |
| `task:create` | ✓ | ✓ | ✓ |
| `task:read_assigned` | ✓ | ✓ | — |
| `task:read` | — | — | ✓ |
| `task:update` | ✓ | ✓ | ✓ |
| `task:transition` | ✓ | ✓ | ✓ |
| `task:assign` | — | — | ✓ |
| `task:verify` | — | ✓ | ✓ |
| `task:delete` | — | — | ✓ |
| `notification:read` | ✓ | ✓ | ✓ |
| `notification:update` | ✓ | ✓ | ✓ |
| `comment:create` | ✓ | ✓ | ✓ |
| `comment:read` | ✓ | ✓ | ✓ |
| `comment:delete` | — | — | ✓ |
| `timeline:read` | ✓ | ✓ | ✓ |

## Implementation
- Add new permissions to existing `permissions` table via init SQL migration
- Add role→permission mappings to `role_permissions` table
- Reuse existing `require_permission` dependency from `auth.py`
- No need to change auth middleware — permission check pattern is already in place
