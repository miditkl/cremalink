# ECAM610 / PrimaDonna Soul statistics

Cremalink can read live machine statistics through the native ECAM `0xA2`
protocol transported via Ayla `data_request` / `data_response`.

This avoids relying on the `d5xx` / `d7xx` Ayla property cache, which can
remain stale for long periods on PrimaDonna Soul machines.

The protocol has been verified on a De'Longhi PrimaDonna Soul ECAM610.75.MB.

## A2 transport

Request:

~~~text
0D 08 A2 0F ID_HI ID_LO COUNT CRC_HI CRC_LO
~~~

The Ayla cloud transport appends a four-byte big-endian Unix timestamp.

Responses contain the first statistic ID/value followed by zero or more
explicit `[ID:uint16, VALUE:uint32]` blocks.

Statistic IDs are sparse.

The tested ECAM610 returns at most 10 statistics in one response, even when
a larger `COUNT` is requested. Cremalink therefore pages by taking the
highest returned ID and requesting again from `last_id + 1`.

## Confirmed ECAM610.75 statistics

| A2 ID | Cremalink name | Meaning |
|---:|---|---|
| 105 | `descale_count` | Number of descales |
| 106 | `total_water_l` | Lifetime water; raw value / 2000 = litres |
| 108 | `filter_replacements` | Number of filter replacements |
| 115 | `grounds_container_clean_count` | Grounds container cleaning/emptying count |
| 3000 | `total_black_beverages` | Machine display category "only coffees" |
| 3001 | `total_milk_coffee_beverages` | First milk/BW category |
| 3002 | `total_other_beverages` | Other beverage category |
| 3003 | `total_milk_only_beverages` | Second milk/white category |
| 3004 | `total_espressos` | Espresso aggregate |
| 3005 | `espresso` | Espresso |
| 3006 | `coffee` | Coffee |
| 3007 | `long_coffee` | Long coffee |
| 3008 | `doppio` | Doppio+ |
| 3009 | `americano` | Americano |
| 3010 | `cappuccino` | Cappuccino |
| 3011 | `latte_macchiato` | Latte Macchiato |
| 3012 | `caffe_latte` | Caffè Latte |
| 3013 | `flat_white` | Flat White |
| 3014 | `espresso_macchiato` | Espresso Macchiato |
| 3015 | `hot_milk` | Hot milk |
| 3016 | `cappuccino_doppio` | Cappuccino Doppio+ |
| 3017 | `cappuccino_mix` | Cappuccino Mix / Reverse |
| 3018 | `hot_water` | Hot water |
| 3019 | `tea` | Tea |
| 3020 | `coffee_pot` | Coffee pot |
| 43010 | `total_beverages` | Overall machine beverage total |

## Derived values

Milk beverages:

~~~text
total_milk_beverages = ID 3001 + ID 3003
~~~

If ID 43010 is unavailable:

~~~text
total_beverages = ID 3000 + ID 3001 + ID 3002 + ID 3003
~~~

Reference ECAM610.75 observation:

~~~text
3000 = 396
3001 = 5231
3002 = 2
3003 = 180

396 + 5231 + 2 + 180 = 5809
43010                  = 5809
~~~

## Unknown statistics

Unknown statistics are deliberately retained by Cremalink.

`Client.get_ecam610_statistics()` returns three sections:

- `known`: confirmed semantic statistics
- `unknown`: every A2 ID without confirmed semantics
- `raw`: the complete unmodified A2 table

Example:

~~~python
{
    "known": {
        "descale_count": 30,
        "total_beverages": 5809,
    },
    "unknown": {
        23000: 152,
        43000: 4797,
    },
    "raw": {
        100: 981155,
    },
}
~~~

No unknown ID is assigned a semantic name merely because its current value
resembles another counter.

Observed but unresolved IDs on the reference ECAM610.75:

~~~text
100
101
109
111
116

3021
3024
3025
3032
3037
3038
3039
3040
3041
3042
3043
3044
3045
3046

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

43000
43005
43011
43012
43014
43015
43016
~~~

The reference values for the higher aggregate-like counters were:

~~~text
23000 =     152
23001 =   21123
23002 =     991
23003 =       6
23004 =   46857
23005 =  705876
23006 = 1133961
23007 =   28495
23008 =   28495
23009 =    1015

43000 = 4797
43005 = 4898
43011 =    0
43012 =    1
43014 =  722
43015 =  245
43016 =    0
~~~

IDs 43000 and 43005 look like aggregate-like counters, but they are not
currently identified as "with milk" or "without milk".

Their values do not fit a simple non-overlapping split of the confirmed
overall beverage total, so assigning such names would currently be
speculative.

ID 3046 had value 4 on the reference machine and therefore matched the old
cached Brew Over Ice count. That numerical match alone is not considered
sufficient evidence for a stable mapping.

## Model-specific caution

A2 statistic meanings are not assumed to be identical across De'Longhi
models or firmware versions.

For example, IDs reported by reverse-engineering work on other machines can
have different apparent semantics on ECAM610.75.

Cremalink therefore only exposes semantic names that have been sufficiently
verified for this model.

## Unknown-ID policy

Cremalink preserves all unrecognised A2 IDs.

This includes:

- IDs already observed on ECAM610.75
- IDs appearing on another firmware version
- IDs appearing on related ECAM610 or ECAM612 variants

Unknown values remain available in both `unknown` and the complete `raw`
table. They are never silently discarded.

## Reverse-engineering policy

For an unknown counter:

1. record a complete A2 snapshot
2. perform exactly one defined machine action
3. record a second snapshot
4. diff the raw IDs
5. repeat the experiment if necessary
6. only add semantic mapping when the behaviour is reproducible

This avoids importing assumptions from other De'Longhi machines into the
stable ECAM610 API.

## Live access

Complete raw A2 table:

~~~python
raw = client.get_all_statistics(dsn)
~~~

Semantic and lossless ECAM610 snapshot:

~~~python
snapshot = client.get_ecam610_statistics(dsn)

known = snapshot["known"]
unknown = snapshot["unknown"]
raw = snapshot["raw"]
~~~

The statistics path is cloud-assisted: the authenticated Ayla service
transports the native A2 command to the machine's Wi-Fi module.

The returned values are live A2 machine statistics rather than the stale
cached Ayla `d5xx` / `d7xx` counters.
