# ECAM A2 Statistics Protocol

> **Status:** reverse-engineered and implemented in `cremalink`; Home Assistant support is implemented in `cremalink-ha`.
>
> **Hardware basis:** De'Longhi PrimaDonna Soul ECAM610.75.MB.
>
> **Family context:** ECAM61X / PrimaDonna Soul. Protocol behavior and semantic mappings must not be assumed to apply unchanged to other De'Longhi firmware families.

## 1. Purpose

De'Longhi coffee machines expose a number of statistics and service properties through the Ayla cloud. On some machines, however, the normal Ayla `d5xx` / `d7xx` property cache can remain stale for long periods and therefore cannot be treated as an authoritative live source.

The ECAM `0xA2` statistics command provides a different path: it asks the machine for its native statistics table and returns current counters directly from the device.

The implementation follows three principles:

1. **A2 is the live source for supported machines.**
2. **Unknown A2 IDs are preserved losslessly rather than guessed.**
3. **Ayla service properties are auxiliary diagnostics only unless freshness and units have been independently established.**

This document describes the protocol, cloud transport, paging rules, current semantic mappings, reverse-engineering policy, and the Home Assistant integration.

---

## 2. Scope and confidence levels

The protocol implementation and mappings described here were developed and tested against a PrimaDonna Soul ECAM610.75.MB.

Three confidence levels are used throughout this document:

- **Confirmed** — validated by protocol structure, machine totals, controlled before/after tests, or multiple independent observations on the tested hardware.
- **Observed** — reproducibly present or changing, but semantic meaning is not yet established.
- **Hypothesis** — plausible interpretation supported by behavior, but intentionally not exposed as a semantic statistic.

Do not transfer a statistic ID from one firmware family to another solely because the numeric ID happens to exist on both.

An ID used by another ECAM model or another reverse-engineering project is not considered confirmed for ECAM61X until its behavior has been independently verified.

---

## 3. Why A2 instead of the normal cloud statistics cache?

### Observed cloud-statistics staleness on the tested machine

On the ECAM610.75.MB used for this reverse engineering, the normal Ayla
service/statistics properties do not appear to be synchronised reliably with
the machine's current counters. Values exposed through the `d5xx`/`d7xx`
properties can lag far behind the live native statistics and may remain
unchanged despite continued machine use.

On this tested machine, this is therefore not merely a theoretical limitation:
the normal Ayla statistics cache does not provide a usable contemporaneous
reference for the live A2 statistics.

This is the main reason why the cloud properties cannot currently be used as
a numerical reference for identifying unknown A2 IDs.

A current A2 snapshot and the corresponding Ayla service properties may
describe very different points in the machine's lifetime. Consequently:

- differing absolute values do **not** disprove equivalent semantics;
- matching values do **not** prove an alias;
- ratios between current A2 values and stale cloud values are meaningless;
- an A2 ID must not be mapped to a `d5xx`/`d7xx` property unless the cloud
  property's freshness has first been established independently.

The cloud property names are therefore used only as semantic clues about
concepts implemented by the firmware. Controlled changes in the live A2 table
remain the primary evidence for A2 mappings.


The Ayla cloud exposes service/statistics properties such as:

```text
d550_water_calc_qty
d551_cnt_coffee_fondi
d552_cnt_calc_tot
d553_water_tot_qty
d554_cnt_filter_tot
d555_water_filter_qty
d556_water_hardness
d558_bev_cnt_desc_on
d7xx beverage counters
```

These names are useful for understanding firmware terminology, but their values may be stale for long periods.

Consequences:

- a cloud value must not invalidate a current A2 value merely because the numbers differ;
- equality between a `d5xx` property and an A2 ID must not be expected;
- a cloud property name does not prove the scaling or unit of its raw value;
- cloud statistics must not be promoted to authoritative live sensors unless freshness has been established.

A2 therefore exists in `cremalink` as an independent live statistics path.

---

## 4. Native ECAM `0xA2` request

The native request frame is:

```text
0D 08 A2 0F ID_H ID_L COUNT CRC_H CRC_L
```

| Offset | Size | Field | Description |
|---:|---:|---|---|
| 0 | 1 | `0x0D` | ECAM request marker |
| 1 | 1 | `0x08` | frame length field |
| 2 | 1 | `0xA2` | statistics command |
| 3 | 1 | `0x0F` | fixed protocol/sub-command byte |
| 4 | 2 | `start_id` | lower statistic-ID bound, big-endian |
| 6 | 1 | `count` | maximum number of existing statistics requested |
| 7 | 2 | CRC | big-endian CRC |

`count` is valid from 1 through 10.

`start_id` is a **lower bound**, not necessarily the ID returned by the machine.

Statistic IDs are sparse. If the requested ID does not exist, the machine returns the first existing statistic whose ID is greater than or equal to `start_id`.

### CRC

The checksum is calculated over all request bytes before the CRC:

```python
from binascii import crc_hqx

crc = crc_hqx(payload, 0x1D0F)
```

The resulting 16-bit value is appended big-endian.

---

## 5. Native ECAM `0xA2` response

The native response layout is:

```text
D0 LEN A2 0F
FIRST_ID_H FIRST_ID_L FIRST_VALUE_4B
[ID_2B VALUE_4B] ...
CRC_H CRC_L
```

| Offset | Size | Field | Description |
|---:|---:|---|---|
| 0 | 1 | `0xD0` | ECAM response marker |
| 1 | 1 | length | response length field |
| 2 | 1 | `0xA2` | statistics command |
| 3 | 1 | `0x0F` | fixed protocol/sub-command byte |
| 4 | 2 | first ID | first returned statistic ID |
| 6 | 4 | first value | first statistic value |
| 10 | 6 × N | further entries | repeated `ID_2B + VALUE_4B` |
| end − 2 | 2 | CRC | big-endian CRC |

The first statistic ID is stored once in the response header area. Every additional statistic contains an explicit two-byte ID followed by a four-byte value.

All currently parsed A2 values are unsigned big-endian integers.

A malformed payload, wrong command byte, invalid CRC, or partial trailing entry is rejected.

---

## 6. Ayla cloud transport

For supported Wi-Fi/cloud-connected ECAM machines, the native A2 packet is transported through the Ayla command properties.

### 6.1 Request wrapping

The native A2 request is followed by a four-byte Unix timestamp:

```text
[NATIVE A2 REQUEST] [UNIX_TIMESTAMP_4B]
```

The timestamp is unsigned and big-endian.

The complete cloud frame is Base64 encoded and written to the Ayla `data_request` property.

Conceptually:

```python
native = build_statistics_request(start_id, count)
sent_at = int(time.time())

cloud_frame = native + sent_at.to_bytes(4, "big")
encoded = base64.b64encode(cloud_frame).decode()
```

### 6.2 Response polling

After sending the request, `cremalink` polls recent `data_response` datapoints.

A response is accepted only when:

- the datapoint value is a string;
- Base64 decoding succeeds;
- the payload is long enough for a native A2 frame plus timestamp;
- byte 0 is `0xD0`;
- byte 2 is `0xA2`;
- the returned first statistic ID is at or above the requested `start_id`;
- the response timestamp is not older than the request timestamp.

The four-byte cloud timestamp is removed before the native packet is passed to the A2 parser.

The timestamp check matters because `data_response` represents recent datapoint history and can contain responses to earlier commands.

---

## 7. Sparse paging

A complete statistics table is larger than one A2 response and must be read page by page.

The machine returns at most ten existing statistics per request.

The algorithm is:

```text
next_id = start_id

repeat:
    request up to N existing statistics >= next_id

    if successful:
        append returned entries

        if returned_count < request_count:
            EOF

        next_id = highest_returned_id + 1

    if timeout:
        do NOT treat as EOF
```

The next request starts at:

```text
last_returned_id + 1
```

and not at:

```text
previous_start_id + count
```

because the ID space is sparse.

### 7.1 EOF rule

**A timeout is never EOF.**

EOF is established only by a successful A2 response containing fewer statistics than the count requested by that successful request.

Example:

```text
requested: 10
returned successfully: 7

=> end of table
```

A timeout proves only that no usable response arrived within the wait period. It does not prove that no further statistic IDs exist.

Treating timeout as EOF can silently truncate the statistics table.

---

## 8. Adaptive timeout handling

Some requests do not reliably succeed with the largest possible page size.

`get_all_statistics()` therefore retries the **same `start_id`** with progressively smaller request counts:

```text
count 10 -> timeout
count  9 -> timeout
count  8 -> success
```

The successful page is then evaluated using `request_count = 8`.

If it contains fewer than eight entries, that successful short response establishes EOF.

After a successful page, the next page starts again with the configured normal page size.

If a request with `count = 1` still times out, the timeout is propagated.

Current retry behavior deliberately prefers correctness over speed:

- keep the same `start_id`;
- reduce `count`;
- retry;
- never convert timeout into EOF.

### Current limitation

There is currently no hard overall deadline for a complete table read.

A sequence of slow cloud timeouts and adaptive retries can therefore make a full refresh considerably longer than a normal successful read.

A future implementation should enforce a monotonic global deadline **inside the synchronous paging loop**.

Simply wrapping the executor call in an asynchronous timeout is unsafe because cancelling the coroutine does not stop the worker thread and could leave A2 requests running in the background.

---

## 9. Python API

### Read one A2 page

```python
page = client.get_statistics(
    dsn,
    start_id=100,
    count=10,
)
```

Synthetic example:

```python
{
    100: 123456,
    101: 789,
    105: 4,
}
```

### Read the complete raw table

```python
raw = client.get_all_statistics(dsn)
```

### Read a semantic ECAM610 snapshot

```python
snapshot = client.get_ecam610_statistics(dsn)
```

Returns a lossless structure:

```python
{
    "known": {
        "total_beverages": 123,
        "espresso": 12,
    },
    "unknown": {
        100: 456789,
    },
    "raw": {
        100: 456789,
        105: 4,
        3005: 12,
        43010: 123,
    },
}
```

Unknown IDs are never discarded.

---

## 10. Progress callback

`get_all_statistics()` and `get_ecam610_statistics()` optionally accept a `progress_callback`.

Callback errors are deliberately isolated from the actual protocol read.

Before a request:

```python
{
    "phase": "request",
    "page": 3,
    "start_id": 3000,
    "request_count": 10,
    "collected_count": 20,
}
```

After a successful page:

```python
{
    "phase": "page_complete",
    "page": 3,
    "start_id": 3000,
    "request_count": 10,
    "returned_count": 10,
    "last_id": 3013,
    "collected_count": 30,
}
```

An adaptive retry naturally generates another `request` event for the same page and `start_id` with a smaller `request_count`.

---

## 11. Confirmed ECAM610.75.MB mappings

These mappings are currently considered confirmed on the tested PrimaDonna Soul ECAM610.75.MB.

They should not automatically be treated as universal ECAM mappings.

### 11.1 Maintenance and lifetime statistics

| A2 ID | Semantic key | Meaning |
|---:|---|---|
| 105 | `descale_count` | completed descale cycles |
| 106 | `total_water_l` | lifetime water quantity |
| 108 | `filter_replacements` | filter replacements |
| 115 | `grounds_container_clean_count` | grounds-container clean/empty count |

ID 106 is converted as:

```python
total_water_l = raw[106] / 2000.0
```

This scaling has been empirically validated on the tested hardware.

### 11.2 Top-level beverage categories

| A2 ID | Semantic key | Meaning |
|---:|---|---|
| 3000 | `total_black_beverages` | black-coffee category |
| 3001 | `total_milk_coffee_beverages` | coffee + milk category |
| 3002 | `total_other_beverages` | other beverage category |
| 3003 | `total_milk_only_beverages` | milk-only category |
| 43010 | `total_beverages` | overall beverage aggregate |

A confirmed invariant is:

```text
43010 = 3000 + 3001 + 3002 + 3003
```

When 43010 is absent, the implementation can derive the overall total from those four categories.

The displayed combined milk total is derived as:

```text
total_milk_beverages = 3001 + 3003
```

### 11.3 Individual and aggregate beverages

| A2 ID | Semantic key | User-facing meaning |
|---:|---|---|
| 3004 | `total_espressos` | espresso-family total |
| 3005 | `espresso` | Espresso |
| 3006 | `coffee` | Coffee |
| 3007 | `long_coffee` | Long |
| 3008 | `doppio` | Doppio+ |
| 3009 | `americano` | Americano |
| 3010 | `cappuccino` | Cappuccino |
| 3011 | `latte_macchiato` | Latte Macchiato |
| 3012 | `caffe_latte` | Caffè Latte |
| 3013 | `flat_white` | Flat White |
| 3014 | `espresso_macchiato` | Espresso Macchiato |
| 3015 | `hot_milk` | Hot Milk |
| 3016 | `cappuccino_doppio` | Cappuccino+ |
| 3017 | `cappuccino_mix` | Cappuccino Mix |
| 3018 | `hot_water` | Hot Water |
| 3019 | `tea` | Tea Function |
| 3020 | `coffee_pot` | Coffee Pot |
| 3037 | `espresso_soul` | Espresso SOUL |
| 3046 | `over_ice` | Over Ice |
| 43000 | `custom_milk_coffee_beverages` | custom milk-coffee aggregate |

#### ID 3016 compatibility note

The existing semantic key is `cappuccino_doppio`.

The tested ECAM61X user interface calls the beverage **Cappuccino+**.

The internal key should be retained for compatibility and stable entity unique IDs. Only the user-facing display name needs correction.

#### ID 3037 — Espresso SOUL

The mapping is supported by the espresso aggregate on the tested machine: the espresso-family total is accounted for by standard Espresso plus Espresso SOUL in the observed dataset.

#### ID 3046 — Over Ice

This mapping closes the otherwise unexplained black-beverage category residual on the tested machine and matches the available ECAM61X beverage set.

#### ID 43000 — custom milk-coffee beverages

This mapping is reinforced by controlled custom-recipe testing.

A custom milk-coffee preparation increments the milk-coffee category and ID 43000 without incrementing an ordinary named milk-coffee recipe counter.

ID 43005 also changed during the relevant test windows, but its exact scope remains unknown and it is deliberately not mapped.

---

## 12. Observed but unidentified A2 IDs

The following IDs have been observed on the tested ECAM610.75.MB and intentionally remain unmapped:

```text
100
101
109
111
116

3021
3024
3025
3032
3038
3039
3040
3041
3042
3043
3044
3045

23000
23001
23002
23003
23004
23005
23006
23007
23008
23009

43005
43011
43012
43014
43015
43016
```

This list is documentation, not an exhaustive whitelist.

Any future raw ID without confirmed semantics is automatically retained in `unknown`.

### 12.1 ID 100

**Status: hypothesis only.**

ID 100 behaves like a maintenance/load accumulator.

In controlled rinse tests it increased in a stable relationship to the live water counter. During clean rinse-only observations:

```text
delta(100) = 7 × delta(106_raw)
```

That relationship does **not** behave like a universal water-volume conversion during beverage operations.

Therefore:

- it is not exposed as water volume;
- it is not mapped to `d550_water_calc_qty`;
- no unit is assigned;
- a descale/water-load interpretation remains plausible but unconfirmed.

### 12.2 ID 109

**Status: strong behavioral observation; semantics unknown.**

Across multiple controlled rinse/water operations:

```text
delta(109) == delta(106_raw)
```

This has been reproducible.

A second water accumulator with a different reset horizon or maintenance context is plausible, but not established.

It must not be labelled `water through filter` merely because `d555_water_filter_qty` exists in Ayla.

### 12.3 ID 111

Unknown. Mappings from other De'Longhi firmware must not be imported simply because the same numeric ID appears elsewhere.

### 12.4 ID 3043

Beverage-related residual, but not identified. UI menu ordering is not evidence for its identity.

### 12.5 IDs 23000–23009

Internal/lifetime statistics. Several change during beverage operations, but units and meanings have not yet been isolated.

### 12.6 ID 43005

Aggregate-like statistic. It has been observed to change alongside custom beverage activity, including ID 43000, but the exact set represented by 43005 has not been established.

---

## 13. Reverse-engineering policy

The mapping policy is intentionally conservative.

### 13.1 Controlled delta testing

Preferred workflow:

1. obtain a complete A2 snapshot;
2. perform exactly one defined machine action;
3. obtain another complete A2 snapshot;
4. calculate all per-ID deltas;
5. repeat or validate against an independent invariant;
6. assign a semantic mapping only when reproducible.

Useful controlled actions include startup rinse, manual rinse, standby rinse, one named beverage, one custom beverage, grounds-container emptying, filter replacement, and a descale cycle.

### 13.2 Do not infer IDs from UI position

The beverage menu is not the protocol ID table.

The ECAM61X UI can reorder recipes by usage while selected entries remain fixed.

Therefore:

```text
menu position != A2 ID
```

### 13.3 Do not infer semantics from magnitude

A large integer might represent scaled water quantity, time, motor/pump runtime, weighted maintenance load, or another internal engineering counter.

Magnitude alone is insufficient evidence.

### 13.4 Preserve unknown values

Unknown IDs must never silently be dropped, given speculative production names, or mapped from another firmware without validation.

---

## 14. Ayla service-property diagnostics

`cremalink` includes a generic property reader:

```python
client.get_property_values(
    dsn,
    [
        "some_property",
        "another_property",
    ],
)
```

A missing property is returned as `None`.

The current ECAM helper reads:

```text
d550_water_calc_qty
d555_water_filter_qty
d556_water_hardness
d512_percentage_to_deca
d513_percentage_usage_fltr
```

using:

```python
client.get_ecam_service_properties(dsn)
```

The generic reader is model-independent; the five-property helper is only a diagnostic convenience.

### 14.1 Cloud properties are not live truth

> **Ayla service/statistics properties may be stale for long periods and must not be treated as a live reference unless freshness has independently been established.**

Therefore, when A2 and Ayla disagree, the discrepancy alone says little: the cloud value may simply be old.

Likewise, coincidental equality is not enough to establish an alias.

### 14.2 Property names do not prove raw units

External reverse-engineering projects associate names such as:

```text
d550_water_calc_qty         -> water/descale calculation
d555_water_filter_qty       -> water through filter
d556_water_hardness         -> water hardness
d512_percentage_to_deca     -> descale-related progress
d513_percentage_usage_fltr  -> filter usage
```

with those Ayla properties.

Real-world raw values do not always resemble the obvious user-facing units implied by those names.

The safe rule is:

> **Treat the property name as evidence for a firmware concept, not as proof of unit, scaling, freshness, or direct A2 equivalence.**

### 14.3 A2 100/109 are not established d550/d555 aliases

No direct mapping is assigned:

```text
A2 100 -> unknown
A2 109 -> unknown
```

Neither is named after its superficially similar cloud property.

Because the corresponding cloud values may themselves be stale, no numeric scaling should be derived from a one-time comparison either.

### 14.4 Useful future service diagnostics

Potentially useful additional properties include:

```text
d551_cnt_coffee_fondi
d552_cnt_calc_tot
d553_water_tot_qty
d554_cnt_filter_tot
d558_bev_cnt_desc_on
d580_service_parameters
```

They may help establish firmware concepts or reset horizons, but remain subject to the same freshness problem.

`d580_service_parameters` is particularly interesting because other reverse-engineering work has found structured descale-related fields inside it.

It is not currently part of `get_ecam_service_properties()`.

---

## 15. Snapshot semantics

A complete A2 table is read sequentially over several requests.

It is therefore **not atomic**.

If the machine dispenses a beverage while the table is being read, an early page can represent a slightly earlier point in time than a later page.

This is normally acceptable for slowly changing lifetime counters, but the result should not be interpreted as a transactional database snapshot.

Future diagnostics should ideally expose:

```text
snapshot_started_at
snapshot_fetched_at
snapshot_duration
```

The current Home Assistant implementation records the completion timestamp of each successful full snapshot.

---

## 16. Home Assistant integration

A2 statistics are deliberately separated from the fast normal machine-monitor coordinator.

### 16.1 Fast monitor coordinator

Normal machine state is polled at:

```text
active/busy: 1 second
standby:     30 seconds
```

The coordinator retains its last known-good monitor snapshot across the first two consecutive transient failures.

A third consecutive failure becomes an update failure.

This prevents an isolated malformed, truncated, or missed monitor response from causing normal entities to flap to unavailable while still exposing sustained communication failures.

### 16.2 Statistics coordinator

A2 lifetime statistics have their own coordinator and are refreshed every 10 minutes because these counters change slowly and a full A2 table is much more expensive than a normal monitor poll.

### 16.3 Timeout retention

If an A2 refresh times out and at least one successful snapshot already exists, Home Assistant retains the previous successful snapshot.

Statistic entities therefore remain available.

The previous `snapshot_fetched_at` is also retained and changes only after a genuinely successful complete A2 read.

If the initial read fails before any usable snapshot exists, the coordinator reports an update failure.

### 16.4 Service-property failures

Service properties are auxiliary diagnostics only.

Failure to fetch them does not invalidate a successful A2 read. The snapshot simply contains:

```python
"service_properties": {}
```

### 16.5 Manual refresh

Home Assistant provides a diagnostic button:

```text
Refresh A2 statistics
```

The button is disabled by default in the entity registry.

While a manual refresh is running, it becomes unavailable, preventing overlapping manual refreshes.

The coordinator tracks:

```text
refresh_in_progress
refresh_started_at
refresh_running_for_seconds
last_refresh_duration_seconds
```

### 16.6 Progress diagnostics

The diagnostic entity exposes the latest A2 progress information:

```text
a2_phase
a2_page
a2_start_id
a2_request_count
a2_returned_count
a2_last_id
a2_collected_count
```

This makes long adaptive refreshes observable without altering protocol behavior.

### 16.7 Raw diagnostic entity

The A2 diagnostic sensor is disabled by default because the raw dictionaries are large and should not normally be written continuously into Home Assistant history.

It exposes:

```text
unknown_statistics
raw_statistics
service_properties
raw_count
snapshot_fetched_at
refresh_in_progress
refresh_started_at
refresh_running_for_seconds
last_refresh_duration_seconds
a2_phase
a2_page
a2_start_id
a2_request_count
a2_returned_count
a2_last_id
a2_collected_count
```

Its entity state is the number of currently unknown A2 IDs.

### 16.8 Statistics sensor semantics

Normal statistics sensors use Home Assistant's `TOTAL_INCREASING` state class.

The lifetime water value is exposed in litres.

---

## 17. Current Home Assistant sensor exposure

Dedicated normal sensors currently include:

```text
Total beverages
Black beverages
Milk beverages
Other beverages
Total water

Milk coffee category
Milk only category
Espressos total

Espresso
Coffee
Long coffee
Doppio+
Americano
Cappuccino
Latte Macchiato
Caffè Latte
Flat White
Espresso Macchiato
Hot milk
Cappuccino Doppio+
Cappuccino Mix
Hot water
Tea
Coffee pot

Descales
Filter replacements
Grounds container cleanings
```

The core already understands these additional confirmed mappings:

```text
3037  Espresso SOUL
3046  Over Ice
43000 custom milk-coffee beverages
```

but dedicated Home Assistant entities for those three are still pending.

The display label for ID 3016 should be changed from `Cappuccino Doppio+` to `Cappuccino+` while preserving the internal key `cappuccino_doppio` for compatibility.

---

## 18. Testing policy

Functional and semantic tests should use **synthetic values**.

Do not make tests depend on one developer's current machine totals.

Good:

```python
raw = {
    3000: 10,
    3001: 20,
    3002: 3,
    3003: 4,
    43010: 37,
}
```

Captured real A2 packets can still be useful as low-level parser regression fixtures because they validate framing, CRC, sparse IDs, and response layout.

The distinction should be:

```text
protocol parser fixtures:
    real captured packets acceptable

semantic / functional tests:
    synthetic values
```

Tests should cover at least:

- request construction;
- CRC validation;
- sparse first-ID behavior;
- response parsing;
- malformed payload rejection;
- complete-table paging;
- successful short-page EOF;
- timeout is not EOF;
- adaptive request-count reduction;
- count=1 timeout propagation;
- progress events;
- progress callback failure isolation;
- unknown-ID preservation;
- confirmed mappings;
- derived aggregates;
- HA stale-snapshot retention;
- service-property failure isolation;
- monitor transient-failure retention.

---

## 19. Model and capability boundaries

The current implementation still uses ECAM610-specific naming because that is the actual validated hardware basis.

Longer term, support should become capability-oriented. For example:

```text
supports_a2_statistics = true
statistics_profile = ecam61x
```

is preferable to assuming that all similarly named De'Longhi machines support the same protocol.

Other De'Longhi Wi-Fi firmware has been observed to accept Ayla command datapoints while silently ignoring native A2 requests.

Support should therefore be established by verified capability rather than brand-wide assumptions.

---

## 20. Known limitations and open questions

### Protocol / transport

Current limitations:

```text
no hard overall A2 refresh deadline
complete snapshot is sequential, not atomic
adaptive cloud retries can be slow
A2 cloud support is not universal across De'Longhi firmware
```

### Monitor interaction

During some long A2 refreshes, transient malformed/truncated normal monitor payloads have been observed.

Home Assistant now tolerates a short sequence of failures, but the underlying reason remains unproven.

Possible causes include truncated payloads, command/monitor contention, cloud response interleaving, or runtime/version mismatch.

None should be documented as the confirmed root cause without additional evidence.

### Semantic reverse engineering

Still unresolved:

```text
100
101
109
111
116
3021
3024
3025
3032
3038-3045
23000-23009
43005
43011
43012
43014
43015
43016
```

Particularly interesting:

```text
100    maintenance/descale-load candidate
109    mirrors raw water deltas during controlled rinses
3043   beverage-related residual
43005  aggregate/custom-related candidate
230xx  internal usage/quantity counters
```

None should receive a production semantic name yet.

---

## 21. Recommended workflow for supporting another machine

When investigating another ECAM model:

1. record exact model and firmware information;
2. verify whether A2 actually produces responses;
3. obtain a complete raw table;
4. preserve every unknown ID;
5. compare protocol structure before semantic mappings;
6. perform controlled before/after tests;
7. validate aggregate equations independently;
8. do not reuse ECAM610 meanings until confirmed;
9. record unsuccessful A2 behavior as well as successful behavior;
10. use synthetic values in semantic unit tests.

Useful contribution data includes model, firmware, transport on which A2 works, an anonymized ID list, controlled deltas, aggregate relationships, and native captured packets where useful.

Never publish account credentials, access/refresh tokens, DSNs, LAN keys, or other account/device secrets.

---

## 22. Relevant implementation files

Core:

```text
cremalink/parsing/statistics.py
cremalink/devices/ecam610_statistics.py
cremalink/clients/cloud.py
```

Home Assistant:

```text
custom_components/cremalink_ha/statistics_coordinator.py
custom_components/cremalink_ha/coordinator.py
custom_components/cremalink_ha/sensor.py
custom_components/cremalink_ha/button.py
```

---

## 23. Related reverse-engineering work

Relevant projects include:

```text
miditkl/cremalink
FrozenGalaxy/PyDeLonghiAPI
sk7n4k3d/delonghi-ha
duckwc/ECAMpy
rtfpessoa/delonghi-comfort-client
mmastrac/longshot
```

These are useful sources for protocol concepts, Ayla property names, model behavior, and independent observations.

Cross-project mappings should still be treated as hypotheses until validated on the target firmware.

---

## 24. Summary

For supported PrimaDonna Soul / ECAM61X hardware, native `0xA2` provides a practical live statistics interface through the Ayla `data_request` / `data_response` transport.

The critical rules are:

1. **A2 statistic IDs are sparse.**
2. **Page from the highest returned ID plus one.**
3. **Timeout is never EOF.**
4. **Only a successful short page proves EOF.**
5. **Preserve unknown IDs losslessly.**
6. **Do not import semantic mappings from another firmware without validation.**
7. **Treat Ayla d5xx/d7xx statistics as potentially stale.**
8. **Do not infer units from cloud property names alone.**
9. **A complete table read is sequential, not atomic.**
10. **Use controlled delta testing and synthetic semantic test data.**

This conservative approach allows reverse-engineered statistics to be used in production without turning plausible guesses into permanent API contracts.
