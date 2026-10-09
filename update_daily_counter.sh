#!/usr/bin/bash
current_date=$(date +'%Y-%m-%d')
TOTAL_LINES=$(find -type f -iname *.go | xargs wc -l | tail -n 1 | awk '{print $1}')

echo "$current_date Total number of lines is: $TOTAL_LINES" >> ./daily_counter.txt
