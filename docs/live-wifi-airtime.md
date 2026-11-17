# Read live Wi-Fi airtime on macOS

The BCM4378 on this M1 MacBook Air returned 98 airtime reports to an ordinary user process on macOS 27.2.1 build 26B131. The sampler used the stock IOReport subscription and update path. The 12-sample series lasted 22.02 seconds with `en0` in station mode on channel 40 at 80 MHz. It received 50 single-valued reports and 48 state reports on every read. [Live observations](../evidence/2026-11-17-live-wifi-airtime.json), [Sampler source](../tools/read_wifi_airtime.m)

| Station report | First standalone sample | All 12 reads in a later series | What it describes |
| --- | ---: | ---: | --- |
| Average CCA | 17% | 18% | The driver's overall channel-busy reading |
| IBSS CCA | 2% | 6% | The same-BSS category, labeled self in the extended firmware report |
| OBSS CCA | 11% | 7% | The overlapping-network category |
| Interference CCA | 3% | 3% | The firmware's interference category |
| CCA excluding own traffic | 14% | 10% | A separate link-quality measurement |

Use these readings together with signal strength and link rate when investigating a slowdown. For example, rising OBSS CCA with steady signal points to contention as a candidate. A rise in the interference category gives a time window to compare against an independent RF measurement. The reports have different update paths. The series retained the same five readings through all 12 samples. [Firmware event and cache trace](cca-provenance.md#native-event-and-cache-path), [Sample data](../evidence/2026-11-17-live-wifi-airtime.json)

The sampler also returned `awdl0` CCA reports, channel records, and five AP load (QBSS) records. The three single-valued QBSS fields were all zero in this run. The AP's BSS Load beacon element and the age of those values remain unverified. [IOReport results](../evidence/2026-11-17-live-wifi-airtime.json)

## State history and freshness

The channel reports have four states labeled 00–25, 25–50, 50–75, and 75–100. Each interface CCA state report has nine labels at 12.5 percentage-point intervals. The driver's interface-average assignment uses integer bands 0–11, 12–24, 25–36, 37–49, 50–61, 62–74, 75–86, 87–99, and 100. Its second bin held the 18% average throughout the series. [Channel state trace](cca-provenance.md#ioreport-catalog-and-sample-path), [Interface state evidence](../evidence/2026-11-17-live-wifi-airtime.json)

Each state has accumulated time and an entry count. On this host the total change over the interval was about 528.48 million ticks, corresponding to the 22.02-second interval at the published 24 MHz timebase. For a continuous counter, the change in one bin divided by the sum of bin changes gives the fraction of **report time** in that bin. Track the channel, association and entry counts along with it. [State deltas](../evidence/2026-11-17-live-wifi-airtime.json)

Channel 144 illustrates why this matters. Its last reported value stayed at zero. Its lowest bin already had one entry, had zero new entries, and accumulated about 22 seconds in 22 seconds of wall time. That advance records time in the existing state. It supplies no evidence that the radio freshly sampled 144. The station remained on channel 40, and the supported-channel list under country code `TR` omitted 144. [Channel 144 counter snapshots](../evidence/2026-11-17-live-wifi-airtime.json), [Channel availability](clm-channel-tables.md)

## Run the sampler

```sh
build_dir="$(mktemp -d)"
xcrun clang -fobjc-arc -Wall -Wextra -Werror \
  -framework Foundation -framework CoreWLAN -framework IOKit \
  -lIOReport tools/read_wifi_airtime.m -o "$build_dir/read_wifi_airtime"
"$build_dir/read_wifi_airtime"
```

One run prints JSON with the current CoreWLAN association, 38 channel values and state records, the interface CCA records, and the QBSS fields. The code uses private libIOReport signatures verified on this build. A sample requests the driver's normal telemetry update, whose code can read firmware power statistics and manage event counters. The active channel and route were checked around the series. [Report update path](cca-provenance.md#ioreport-catalog-and-sample-path)

The separate CoreWiFi client created with its default service returned empty values for current CCA, cached link quality, MCS, guard interval, and spatial streams in the unprivileged test. IOReport supplied the airtime values above. [Service probe results](../evidence/2026-11-17-live-wifi-airtime.json)
