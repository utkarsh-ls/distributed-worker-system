#!/bin/bash

mkdir -p .prometheus_data

prometheus \
  --config.file=./monitoring/prometheus.yml \
  --storage.tsdb.path=./.prometheus_data \
  --web.listen-address=":9090"