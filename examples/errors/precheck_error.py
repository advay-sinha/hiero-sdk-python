"""
uv run examples/errors/precheck_error.py
python examples/errors/precheck_error.py

Demonstrates how to catch and inspect PrecheckError before a transaction
is submitted for consensus.
"""

import os
import sys

from dotenv import load_dotenv

from hiero_sdk_python import (
    AccountId,
    Client,
    Hbar,
    Network,
    PrivateKey,
    ResponseCode,
    TransferTransaction,
)
from hiero_sdk_python.exceptions import PrecheckError

load_dotenv()


NETWORK_NAME = os.getenv("NETWORK", "testnet").lower()
BOGUS_ACCOUNT_ID_STR = os.getenv("PRECHECK_ERROR_RECIPIENT", "0.0.999999")
try:
    BOGUS_ACCOUNT_ID = AccountId.from_string(BOGUS_ACCOUNT_ID_STR)
except (TypeError, ValueError):
    print("Missing or invalid PRECHECK_ERROR_RECIPIENT in .env")
    sys.exit(1)


def setup_client():
    """Build a client from .env operator credentials."""
    network = Network(NETWORK_NAME)
    client = Client(network)

    try:
        operator_id = AccountId.from_string(os.getenv("OPERATOR_ID", ""))
        operator_key = PrivateKey.from_string(os.getenv("OPERATOR_KEY", ""))
    except (TypeError, ValueError):
        print("Missing or invalid OPERATOR_ID/OPERATOR_KEY in .env")
        sys.exit(1)

    client.set_operator(operator_id, operator_key)
    return client, operator_id


def trigger_precheck_error(client, operator_id):
    """
    Attempt to send HBAR to an obviously invalid account so the SDK raises
    PrecheckError. This lets us inspect err.status and err.transaction_id.
    """
    print("Attempting a transfer that should fail precheck...")
    try:
        (
            TransferTransaction()
            .add_hbar_transfer(operator_id, Hbar.from_tinybars(-10_000))
            .add_hbar_transfer(BOGUS_ACCOUNT_ID, Hbar.from_tinybars(10_000))
            .freeze_with(client)
            .execute(client)
        )
    except PrecheckError as err:
        status_name = ResponseCode(err.status).name
        tx_id = err.transaction_id
        print(
            "Precheck failed",
            f"status={status_name} ({err.status})",
            f"transactionId={tx_id}",
        )
        return
    except Exception as err:
        print(f"Unexpected exception type: {err}")
        return

    print(
        "Transfer unexpectedly passed precheck. "
        "Set PRECHECK_ERROR_RECIPIENT to an invalid account ID."
    )


def main():
    client, operator_id = setup_client()
    trigger_precheck_error(client, operator_id)


if __name__ == "__main__":
    main()
