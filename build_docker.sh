#!/bin/bash
NAMESPACE="${1:-codebase_b1113_app}"
docker build -t "$NAMESPACE" .