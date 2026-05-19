spark-submit \
  --class WebLogTrafficStats \
  --master local[*] \
  target/scala-2.12/weblog-traffic-stats_2.12-0.1.0.jar \
  sample_web_logs.csv
