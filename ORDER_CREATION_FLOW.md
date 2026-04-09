# Order Creation Flow — Event Flow Diagram

## Overview

This diagram traces the complete order creation flow from API call through all asynchronous events,
including **idempotency checks** and **duplicate prevention** at each step.

---

## Complete Flow Diagram (Mermaid)

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant APIGateway
    participant OrderService
    participant OrderDB
    participant OutboxTable
    participant OutboxPoller
    participant RabbitMQ
    participant ProductService
    participant ProductDB
    participant Redis
    participant NotificationService

    rect rgb(230, 255, 230)
    Note over Client,OrderDB: PHASE 1: Order Creation (Synchronous — HTTP)

    Client->>APIGateway: POST /orders
    APIGateway->>OrderService: Forward POST /orders

    OrderService->>OrderDB: BEGIN TRANSACTION (nested)
    OrderService->>OrderDB: 1. Create OrderAddress
    OrderService->>OrderDB: 2. Create Order (status=PENDING)
    OrderService->>OrderDB: 3. Create OrderItems
    OrderService->>OutboxTable: 4. Insert OutboxEvent: "order.created"<br/>(payload: OrderCreatedEvent)
    OrderService->>OutboxTable: 5. Insert OutboxEvent: "inventory.reserve.requested"<br/>(payload: InventoryReserveRequested)
    OrderDB-->>OrderService: COMMIT

    OrderService-->>APIGateway: 201 Created (OrderSchema)
    APIGateway-->>Client: 201 Created
    end

    rect rgb(255, 255, 220)
    Note over OutboxPoller,RabbitMQ: PHASE 2: Outbox Polling & Publishing (Async — Background Task)

    loop Every 500ms
        OutboxPoller->>OutboxTable: SELECT * WHERE processed=false LIMIT 50
        OutboxTable-->>OutboxPoller: Unprocessed events

        alt Event: "order.created"
            OutboxPoller->>RabbitMQ: Publish to "order.events.queue"<br/>(OrderCreatedEvent)
            OutboxPoller->>OutboxTable: Mark as processed
        else Event: "inventory.reserve.requested"
            OutboxPoller->>RabbitMQ: Publish to "product.inventory.events"<br/>(InventoryReserveRequested)
            OutboxPoller->>OutboxTable: Mark as processed
        end
    end
    end

    rect rgb(255, 230, 230)
    Note over ProductService,ProductDB: PHASE 3: Inventory Reservation (Async — Product Service Consumer)

    RabbitMQ->>ProductService: Consume "product.inventory.events"<br/>(InventoryReserveRequested)

    ProductService->>Redis: CHECK idempotency:<br/>key = "{prefix}:inventory.reserve.requested:{event_id}"

    alt Already processed (key exists)
        Redis-->>ProductService: TRUE (duplicate)
        ProductService-->>RabbitMQ: ACK & SKIP (no re-processing)
    else Not yet processed
        Redis-->>ProductService: FALSE (new event)
        ProductService->>ProductDB: reserve_inventory(items)<br/>(validate stock for ALL items — atomic)

        alt Stock SUFFICIENT
            ProductDB-->>ProductService: reserved_items[]
            ProductService->>Redis: MARK processed<br/>(result="succeeded", TTL=24h)
            ProductService->>RabbitMQ: Publish to "order.saga.response"<br/>(InventoryReserveSucceeded)
        else Stock INSUFFICIENT
            ProductDB-->>ProductService: Failed
            ProductService->>Redis: MARK processed<br/>(result="failed", TTL=24h)
            ProductService->>RabbitMQ: Publish to "order.saga.response"<br/>(InventoryReserveFailed)
        end
    end
    end

    rect rgb(230, 230, 255)
    Note over OrderService,Redis: PHASE 4: SAGA Response Handling (Async — Order Service Consumer)

    RabbitMQ->>OrderService: Consume "order.saga.response"

    alt InventoryReserveSucceeded
        OrderService->>Redis: CHECK idempotency:<br/>key = "{prefix}:inventory.reserve.succeeded:{event_id}"

        alt Already processed
            Redis-->>OrderService: TRUE (duplicate)
            OrderService-->>RabbitMQ: ACK & SKIP
        else Not yet processed
            Redis-->>OrderService: FALSE (new event)
            OrderService->>OrderDB: UPDATE order SET status=CONFIRMED
            OrderService->>RabbitMQ: Publish to "order.events.queue"<br/>(OrderConfirmedEvent)
            OrderService->>Redis: MARK processed<br/>(result="success", TTL=24h)
        end

    else InventoryReserveFailed
        OrderService->>Redis: CHECK idempotency:<br/>key = "{prefix}:inventory.reserve.failed:{event_id}"

        alt Already processed
            Redis-->>OrderService: TRUE (duplicate)
            OrderService-->>RabbitMQ: ACK & SKIP
        else Not yet processed
            Redis-->>OrderService: FALSE (new event)
            OrderService->>OrderDB: UPDATE order SET status=CANCELLED
            OrderService->>RabbitMQ: Publish to "order.events.queue"<br/>(OrderCancelledEvent)
            OrderService->>Redis: MARK processed<br/>(result="success", TTL=24h)
        end
    end
    end

    rect rgb(255, 240, 220)
    Note over RabbitMQ,NotificationService: PHASE 5: Downstream Notifications (Async)

    RabbitMQ->>NotificationService: Consume "order.events.queue"

    alt OrderConfirmedEvent
        NotificationService->>NotificationService: Send order confirmation email
    else OrderCancelledEvent
        NotificationService->>NotificationService: Send cancellation email
    else OrderCreatedEvent
        NotificationService->>NotificationService: Log/track order creation
    end
    end
```

---

## RabbitMQ Queue Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RabbitMQ Que                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────┐                                               │
│  │  order.events.queue      │◄──── OrderService (publishes)                │
│  │  (DLQ: order.events.dlq) │     - OrderCreatedEvent                       │
│  └──────────────────────────┘     - OrderConfirmedEvent                     │
│           │                       - OrderCancelledEvent                     │
│           │                                                                │
│           ▼                                                                │
│  ┌──────────────────────────┐                                               │
│  │  Notification Service    │     Handles email notifications               │
│  └──────────────────────────┘                                               │
│                                                                             │
│  ┌──────────────────────────┐                                               │
│  │  product.inventory.events│◄──── OrderService (publishes)                │
│  │  (DLQ: ...events.dlq)    │     - InventoryReserveRequested               │
│  └──────────────────────────┘     - InventoryReleaseRequested               │
│           │                                                                │
│           ▼                                                                │
│  ┌──────────────────────────┐                                               │
│  │  Product Service         │     Reserves/releases inventory               │
│  └──────────────────────────┘                                               │
│                                                                             │
│  ┌──────────────────────────┐                                               │
│  │  order.saga.response     │◄──── Product Service (publishes)             │
│  │  (DLQ: ...response.dlq)  │     - InventoryReserveSucceeded               │
│  └──────────────────────────┘     - InventoryReserveFailed                  │
│           │                                                                │
│           ▼                                                                │
│  ┌──────────────────────────┐                                               │
│  │  Order Service (Consumer)│     Confirms/cancels order                    │
│  └──────────────────────────┘                                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Idempotency & Duplicate Prevention Analysis

### Where Duplicates Could Occur & How They're Prevented

| # | Potential Duplicate Scenario | Prevention Mechanism | Status |
|---|------------------------------|---------------------|--------|
| 1 | **Outbox poller picks up same event twice** (poll runs before mark-as-processed) | OutboxTable: `processed` flag set AFTER publish; next poll skips `processed=true` rows | ✅ Safe |
| 2 | **RabbitMQ redelivers message** (consumer crashes before ACK) | Redis idempotency check: `is_event_processed(event_id, event_type)` returns `true` for duplicates | ✅ Safe |
| 3 | **Product service receives same `inventory.reserve.requested` twice** | Redis key: `{prefix}:inventory.reserve.requested:{event_id}` — checked BEFORE any DB operation | ✅ Safe |
| 4 | **Order service receives same `inventory.reserve.succeeded` twice** | Redis key: `{prefix}:inventory.reserve.succeeded:{event_id}` — checked BEFORE status update | ✅ Safe |
| 5 | **Order service receives same `inventory.reserve.failed` twice** | Redis key: `{prefix}:inventory.reserve.failed:{event_id}` — checked BEFORE status update | ✅ Safe |
| 6 | **Two outbox poller tasks run simultaneously** | Single background task via `asyncio.create_task()` in lifespan — only ONE instance | ✅ Safe |

### Redis Idempotency Key Format

```
{service_prefix}:{event_type}:{event_id}
```

**Examples:**
```
product-service:inventory.reserve.requested:550e8400-e29b-41d4-a716-446655440000
order-service:inventory.reserve.succeeded:550e8400-e29b-41d4-a716-446655440000
order-service:inventory.reserve.failed:550e8400-e29b-41d4-a716-446655440000
```

**TTL:** 24 hours (after which key expires; event could theoretically be reprocessed, but `event_id` is UUID4 so collision probability is negligible)

---

## Critical Flow Analysis

### ✅ What's Correct

1. **Outbox pattern** — Events are created in the SAME DB transaction as the order (atomicity).
2. **Idempotency at consumer level** — Each consumer checks Redis BEFORE processing.
3. **Failed events are also marked as processed** — Prevents infinite retry loops.
4. **Single poller instance** — Only one background task runs.

### ⚠️ Potential Issues

| # | Issue | Impact | Recommendation |
|---|-------|--------|----------------|
| 1 | **`event_id` generated in event schema constructor** — If outbox poller re-serializes the payload, the `event_id` is preserved from the original event (✅ safe), but if any service creates a NEW event with a NEW `event_id` for the same logical operation, idempotency breaks | Medium | Ensure `event_id` is ALWAYS preserved from the original outbox event — never regenerate |
| 2 | **Outbox poller marks event as processed BEFORE consumer ACKs** — If RabbitMQ publish fails AFTER outbox marks as processed, the event is lost (not retried) | Medium | Consider marking as processed AFTER successful publish confirmation |
| 3 | **No idempotency check for `order.created` event** in notification service — If notification service crashes and reprocesses, duplicate emails could be sent | Low | Add Redis idempotency in notification service consumers |
| 4 | **Redis TTL of 24h** — If system is down >24h and backlog is processed, idempotency keys may have expired | Low (edge case) | Consider longer TTL (48-72h) or persistent idempotency store for critical events |

---

## State Transitions Summary

```
Order Status Flow:
┌─────────┐     ┌─────────┐
│ PENDING │────▶│CONFIRMED│  (inventory.reserve.succeeded)
└────┬────┘     └─────────┘
     │
     │             ┌───────────┐
     └────────────▶│ CANCELLED │  (inventory.reserve.failed)
                   └───────────┘

Outbox Event Flow:
┌──────────────┐     ┌───────────────┐
│ processed=F  │────▶│ processed=T   │
│ (unprocessed)│     │ (processed)   │
└──────────────┘     └───────────────┘

Redis Idempotency Flow:
┌──────────────┐     ┌───────────────┐
│ Key NOT set  │────▶│ Key SET       │
│ (new event)  │     │ (processed)   │
└──────────────┘     └───────────────┘
```

---

## Files Involved in This Flow

| Service | File | Role |
|---------|------|------|
| **Order Service** | `service_layer/order_service.py` | Creates order + outbox events |
| **Order Service** | `service_layer/outbox_poller_service.py` | Polls & publishes events to RabbitMQ |
| **Order Service** | `service_layer/outbox_event_service.py` | Manages outbox event CRUD |
| **Order Service** | `events_publisher/order_event_publisher.py` | Publishes events to RabbitMQ |
| **Order Service** | `events_consumer/order_event_consumer.py` | Consumes SAGA responses |
| **Product Service** | `event_consumer/product_event_consumer.py` | Consumes inventory requests |
| **Product Service** | `event_publisher/event_publisher.py` | Publishes SAGA responses |
| **Shared** | `shared/idempotency_service.py` | Redis-based deduplication |
| **Shared** | `shared/schemas/event_schemas.py` | Pydantic event models |
| **Shared** | `shared/enums/event_enums.py` | Event type & queue enums |
