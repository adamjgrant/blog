#!/bin/bash
# Runs every PastPages group in sequence; state goes to data_pastpages/JOB_STATUS.
cd "$(dirname "$0")"
S=data_pastpages/JOB_STATUS
mkdir -p data_pastpages
for g in newspapers outlets intl; do
  echo "running $g" > $S
  python3 pastpages.py run --group $g >/dev/null 2>&1 || { echo "failed $g exit=$?" > $S; exit 1; }
done
echo "finished" > $S
