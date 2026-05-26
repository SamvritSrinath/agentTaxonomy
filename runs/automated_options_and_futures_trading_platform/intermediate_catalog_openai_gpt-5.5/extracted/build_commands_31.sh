# set DISABLE_FEED=true in backend/.env, restart backend, then:
curl -X POST 'http://localhost:8000/api/dev/price?symbol=SPY&price=100'
curl -X POST 'http://localhost:8000/api/dev/price?symbol=SPY&price=97.5'
curl 'http://localhost:8000/api/trades'
