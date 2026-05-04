"""Cloud-native storage backends for AWS deployments.

Each module here mirrors a `Protocol` defined in the domain modules
(applied/store.py, letters/store.py, etc.) and substitutes the
file-backed implementation with an S3 or DynamoDB one. Wiring is
gated on `Settings.storage_backend == "aws"` in the route factories.
"""
