# companies-house

A Python client for the Companies House API that stays inside the rate limit instead of finding it by getting banned.

```python
from companies_house import CompaniesHouse

ch = CompaniesHouse("your-ch-api-key")      # pip install companies-house
print(ch.company("445790")["company_name"])  # TESCO PLC
```

Free to use with your own Companies House API key, which is also free: [how to get one, step by step](https://registrum.co.uk/guides/how-to-get-a-companies-house-api-key), and [what to check if it returns 401](https://registrum.co.uk/guides/companies-house-api-key-not-working). One dependency (`httpx`), Python 3.9+, typed, returns plain dicts.

## What it covers

```python
ch.search("tesco")                       # one page of search results
ch.officers("445790")                    # directors and secretaries
ch.psc("445790")                         # persons with significant control
ch.filing_history("445790", category="accounts")
ch.charges("445790")

for company in ch.iter_search("tesco", limit=250):   # pages for you
    ...
for filing in ch.iter_filing_history("445790"):
    ...
```

Company numbers are normalised for you: `445790` becomes `00445790`, `sc123456` becomes `SC123456`.

## Rate limits

Companies House allows a fixed number of requests per key in a five minute window (documented as 600) and bans keys that keep going after they are told to stop. This client:

- reads `X-Ratelimit-Remain` and `X-Ratelimit-Reset` from every response and sleeps until the window resets when you are nearly out, so it does not trigger the 429 in the first place;
- on a 429, waits for `Retry-After` or the reset time, then retries a bounded number of times before raising `RateLimited`;
- retries 502, 503 and 504 with backoff, also bounded;
- never sleeps longer than `max_wait` seconds (310 by default); past that it raises instead of hanging.

```python
from companies_house import CompaniesHouse, NotFound, RateLimited, AuthError

ch = CompaniesHouse(key, max_retries=3, low_watermark=5, max_wait=310)
try:
    ch.company("00000000")
except NotFound:
    ...
except RateLimited as e:
    print("try again in", e.retry_after, "seconds")
except AuthError as e:
    print(e)        # explains Basic auth, key type, live vs sandbox

print(ch.rate_limit.remaining, "of", ch.rate_limit.limit, "left")
```

The clock and sleep are injectable (`clock=`, `sleep=`), so you can test your own code against it.

## Need financials or ownership chains?

The official API returns filing metadata, not figures, and gives you one PSC level at a time. [Registrum](https://registrum.co.uk/?utm_source=pypi) is a hosted API over the same data that adds structured financials from filed accounts and the full ownership chain to the people at the top. The client has the same shape:

```python
from companies_house import Registrum

reg = Registrum("your-registrum-key")        # or set REGISTRUM_API_KEY
reg.financials("445790")                     # figures from filed accounts, where available
reg.psc_chain("445790")                      # follows corporate owners upwards
reg.bundle("445790", include=["profile", "financials", "psc"])
```

No key yet? Ask for a trial with an email address:

```python
reg = Registrum()
reg.start_trial("you@example.com")           # we email a confirmation link
```

The key does not work until you click that link; until then calls raise `TrialUnverified` with the reason. Limits and plans are on the [pricing page](https://registrum.co.uk/pricing?utm_source=pypi).

## Notes

- Synchronous only for now.
- Sends `User-Agent: companies-house-python/<version>` so the services you call can see which client is talking to them.
- Not affiliated with Companies House. Contains public sector information licensed under the Open Government Licence v3.0.

Issues and pull requests are welcome. Security reports: see [SECURITY.md](SECURITY.md). MIT licence.
