# Precheck Errors

Developers often assume that if `execute()` finishes without raising an exception, their Hedera transaction or query succeeded. The SDK makes earlier failure modes explicit by raising dedicated exceptions defined in `src/hiero_sdk_python/exceptions.py`. Understanding the difference between **precheck failures**, **network retry exhaustion**, and **receipt status errors** helps you prevent silent production outages and instrument the right alerts.

## Failure Phases in `_Executable._execute`

Every transaction/query inherits the execution pipeline implemented in `src/hiero_sdk_python/executable.py`. It can fail in three distinct moments:

1. **Precheck (throws `PrecheckError`)** – the node rejects the protobuf request before consensus. Common causes are malformed transactions, invalid IDs, insufficient payer balance, missing signatures, or submitting to the wrong ledger.
2. **Network/Node retry exhaustion (throws `MaxAttemptsError`)** – the SDK retried with exponential backoff and still could not get a valid response (e.g., repeated `UNAVAILABLE`, throttling, or node timeouts).
3. **Receipt status errors (throws `ReceiptStatusError`)** – the transaction reached consensus but the receipt status is not `ResponseCode.SUCCESS` (for example `INSUFFICIENT_PAYER_BALANCE` after consensus or a failed scheduling precondition).

Because each error type represents a different phase, you should **log and handle them separately**. This makes it easy to distinguish configuration mistakes (precheck) from infrastructure issues (network retries) and business failures (receipt status).

## What is a `PrecheckError`?

`PrecheckError` surfaces rejection **before consensus**. The node validated the transaction envelope and determined it can never succeed if submitted unchanged. Typical triggers include:

- Invalid or non-existent account/topic/file ID references.
- Negative or out-of-range transfers/fees.
- Signatures that are missing, expired, or do not match the public keys on the payer.
- Using a transaction ID that has already been used, is too far in the future, or outside its valid duration.
- Trying to submit to a node that is not part of your chosen network map (e.g., mixing testnet/mainnet node addresses).

The exception exposes two helpful attributes:

- `status` – the raw `ResponseCode` from the node (use `ResponseCode(status).name` for readability).
- `transaction_id` – the `TransactionId` that was rejected, when available.

Because `PrecheckError` inherits from `Exception`, you can catch it explicitly and decide whether to adjust input, alert an operator, or raise a user-friendly error upstream.

## Handling Precheck Failures

Always highlight the status code and the transaction ID in your logs/metrics so incidents can be triaged quickly. The following pattern is recommended:

```python
"""
python examples/errors/precheck_error.py
"""
import logging

from hiero_sdk_python import Client, Network, TransferTransaction, Hbar, AccountId, ResponseCode
from hiero_sdk_python.exceptions import PrecheckError

client = Client(Network("testnet"))
client.set_operator(AccountId.from_string("0.0.1234"), "<operator-private-key>")

try:
    (
        TransferTransaction()
        .add_hbar_transfer("0.0.1234", -Hbar.from_tinybars(10))  # payer
        .add_hbar_transfer("0.0.999999", Hbar.from_tinybars(10))  # bogus recipient
        .freeze_with(client)
        .execute(client)
    )
except PrecheckError as err:
    status_name = ResponseCode(err.status).name
    logging.error(
        "Precheck failed",
        extra={
            "status": status_name,
            "status_code": err.status,
            "transaction_id": str(err.transaction_id),
        },
    )
    # Retry with corrected input or exit early.
    raise
```

The snippet intentionally uses a bogus account ID so that the SDK raises a `PrecheckError`. The log captures **what** failed (`INVALID_ACCOUNT_ID`, for example) and **which transaction** needs investigation.

## Best Practices

- **Short-circuit when precheck fails.** Retrying the exact same protobuf will never succeed until you fix the request.
- **Normalize metrics per stage.** Precheck spikes usually signal code regressions or misconfigured environments, not network instability.
- **Surface the response code.** `ResponseCode` already encodes the node feedback; include both numeric and named values.
- **Teach new team members the three-stage mental model.** First validate inputs (precheck), then trust the retry/backoff strategy, finally confirm success via receipts.

## Further Reading

- Example script: `examples/errors/precheck_error.py`.
- Receipt handling guide: `docs/sdk_developers/training/receipts.md`.
- Exception definitions: `src/hiero_sdk_python/exceptions.py`.