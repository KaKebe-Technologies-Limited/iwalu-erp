# Notifications & Alerts Module

**App**: `notifications`  
**Type**: Tenant-scoped  
**Phase**: 6b  

---

## Overview

Multi-channel notification system delivering alerts based on system events (low fuel, low stock, variance, approvals). Supports in-app, email, and SMS channels with user-configurable preferences and admin-managed templates.

---

## Models

### Notification
In-app notification record delivered to a specific user.

| Field | Type | Notes |
|-------|------|-------|
| recipient_id | IntegerField | User PK (cross-schema safe) |
| notification_type | CharField | low_fuel, low_stock, variance_alert, shift_reminder, payment_failure, approval_required, system |
| channel | CharField | in_app, email, sms |
| priority | CharField | low, normal, high, critical |
| title | CharField(255) | Short alert title |
| body | TextField | Full alert message |
| source_type | CharField | Model name that triggered notification |
| reference_id | IntegerField | PK of the source object |
| read_at | DateTimeField | Null if unread |
| created_at | DateTimeField | Auto |
| updated_at | DateTimeField | Auto |

**Indexes**: (recipient_id, -created_at), (recipient_id, read_at), (notification_type, -created_at)

### NotificationPreference
User opt-in/opt-out per notification type and channel.

| Field | Type | Notes |
|-------|------|-------|
| user_id | IntegerField | User PK |
| notification_type | CharField | Same choices as Notification |
| channel | CharField | in_app, email, sms |
| is_enabled | BooleanField | Default True |

**Unique constraint**: (user_id, notification_type, channel)

### NotificationTemplate
Admin-managed message templates with variable substitution.

| Field | Type | Notes |
|-------|------|-------|
| notification_type | CharField | Same choices as Notification |
| channel | CharField | in_app, email, sms |
| subject | CharField(255) | Template subject line |
| body | TextField | Body with {variable} placeholders |
| variables | JSONField | List of available variable names |
| is_active | BooleanField | Default True |

**Unique constraint**: (notification_type, channel)

---

## API Endpoints

### Notifications (user's own)
```
GET    /api/notifications/                 List (filter: notification_type, channel, priority, is_read)
GET    /api/notifications/{id}/            Retrieve
GET    /api/notifications/unread-count/    Unread count
POST   /api/notifications/{id}/read/       Mark as read
POST   /api/notifications/read-all/        Bulk mark as read (optional: notification_type)
DELETE /api/notifications/{id}/            Delete own notification
```

### Notification Preferences (user's own)
```
GET    /api/notification-preferences/                    List preferences
POST   /api/notification-preferences/update-preference/  Create/update a preference
```

### Notification Templates (admin/manager write)
```
GET    /api/notification-templates/              List
POST   /api/notification-templates/              Create (admin/manager)
GET    /api/notification-templates/{id}/         Retrieve
PATCH  /api/notification-templates/{id}/         Update (admin/manager)
DELETE /api/notification-templates/{id}/         Delete (admin/manager)
POST   /api/notification-templates/{id}/preview/ Preview with context
```

---

## Permissions

| Action | Required Role |
|--------|--------------|
| View own notifications | All authenticated |
| Mark read / delete own | All authenticated |
| View/update own preferences | All authenticated |
| View templates | All authenticated |
| Create/update/delete templates | Admin, Manager |

---

## Service Functions

| Function | Purpose |
|----------|---------|
| `create_notification()` | Create notification, respecting preferences |
| `create_notification_from_template()` | Create using a registered template |
| `mark_read()` | Mark single notification as read |
| `mark_all_read()` | Bulk mark read, optional type filter |
| `get_unread_count()` | Count unread in-app notifications |
| `notify_low_fuel()` | Alert trigger for low tank levels |
| `notify_low_stock()` | Alert trigger for low product stock |
| `notify_variance_alert()` | Alert trigger for fuel variance |
| `notify_approval_required()` | Alert trigger for pending approvals |

---

## Integration Points

| From Module | Event | Notification Type |
|-------------|-------|-------------------|
| fuel (Tank) | current_level <= reorder_level | low_fuel |
| products/inventory | stock_quantity < reorder_level | low_stock |
| fuel (FuelReconciliation) | variance outside tolerance | variance_alert |
| finance/inventory | transaction > approval threshold | approval_required |

---

## Tests

- **Service tests**: Create, opt-out suppression, mark read, mark all read, unread count, template rendering
- **API tests**: List own, filter unread, unread count, mark read, read all, permission checks
- **Preference tests**: List, create/update toggle
- **Template tests**: CRUD permissions, preview rendering

---

## Future (Phase 6c)

- Email delivery via SMTP (currently stubbed)
- SMS delivery via MTN/Airtel APIs (currently stubbed)
- Celery task queue for async delivery
