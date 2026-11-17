# BCM4378 firmware feature index

This index records **128 distinct words** across the saved live reply, the identical 86-word
legacy table in both signed driver slices, and the separate legacy `csi` check. The M1 Air's reply
contains **90 words and 89 distinct values**. `txcap` is the repeated word. Forty-eight of
the 86 table words occur in that reply. [Saved words and legacy mapping](../evidence/2026-11-17-live-firmware-capabilities.json)

The extended parser can directly set **84** bit indices and clear **19** in both slices.
Eighteen indices appear in both call sets. A shared callsite accepts eight different values.
The operations describe what the compiled parser can do. Active bits depend on the reply
and host policy. [Per-slice direct-call evidence](../evidence/2026-11-17-extended-firmware-capabilities.json),
[Parser and hardware context](extended-firmware-capabilities.md)

## Words and mapped bits

A count of zero marks a word absent from the saved reply. A dash marks an unmapped bit
or operation. The legacy method also handles `ap` and `hp2p` in the
separate paths recorded below the table.

| Exact word | Occurrences in saved reply | Legacy table bit or separate CSI bit | Direct extended update of that bit |
| --- | ---: | ---: | --- |
| `6g` | 0 | 93 | Set and clear |
| `802.11d` | 1 | — | — |
| `802.11h` | 1 | — | — |
| `adv_ecounters` | 1 | 89 | Set |
| `ampdu` | 1 | — | — |
| `ampdu_rx` | 1 | — | — |
| `ampdu_tx` | 1 | — | — |
| `amsdurx` | 1 | — | — |
| `amsdutx` | 1 | — | — |
| `anqpo` | 1 | 17 | Set |
| `ap` | 1 | 16 | Set and clear |
| `arb` | 1 | — | — |
| `arpoe` | 1 | — | — |
| `avoid-bssid` | 1 | 83 | Set |
| `awd_data_info` | 0 | 35 | — |
| `awdl` | 1 | — | — |
| `bcntrim` | 0 | 57 | Set |
| `bdo` | 1 | 45 | Set |
| `bkoff_evt` | 1 | 61 | Set |
| `bsstrans` | 1 | 37 | Set |
| `bt5gcx` | 0 | 120 | Set |
| `btc_wifi_prot` | 1 | 15 | Set |
| `cac` | 1 | — | — |
| `cdef` | 1 | 29 | Set |
| `chstats` | 0 | 103 | Set |
| `clm_restrict` | 1 | 62 | Set |
| `cptlv-4` | 1 | — | — |
| `cqa` | 1 | — | — |
| `csi` | 0 | 97 (separate check) | — |
| `d11status` | 1 | — | — |
| `dfrts` | 1 | 10 | Set |
| `dfsp` | 1 | 54 | Set |
| `dsa` | 0 | 79 | Set |
| `dtim_miss` | 1 | 110 | — |
| `dualband` | 1 | 28 | Set |
| `dynbw` | 0 | 102 | Set and clear |
| `ecounters` | 1 | 74 | Set |
| `epno` | 1 | 27 | Set |
| `etd_info` | 1 | — | — |
| `event_log` | 1 | — | — |
| `evt_ext` | 1 | 34 | Set |
| `fbt_adpt` | 1 | — | — |
| `fbtoverds` | 1 | 32 | Set |
| `fie` | 1 | 77 | Set |
| `gcmp` | 1 | 66 | Set and clear |
| `hchk` | 1 | — | — |
| `he` | 1 | 67 | Set |
| `hp2p` | 1 | — | — |
| `hwrng` | 1 | — | — |
| `icmp` | 1 | — | — |
| `idauth` | 1 | 12 | Set |
| `idsup` | 1 | — | — |
| `ifst` | 1 | 53 | Set |
| `ifver` | 1 | — | — |
| `iot_bd` | 1 | 87 | Set and clear |
| `iot_bm` | 1 | 82 | Set and clear |
| `lpas` | 1 | 26 | Set |
| `lpc` | 0 | 113 | — |
| `lpr_scan` | 1 | 60 | Set |
| `lr154cx` | 0 | 111 | Set |
| `ltecx` | 0 | 73 | Set |
| `ltecxlbt` | 0 | 80 | Set |
| `mfp` | 1 | 38 | Set |
| `mimo_ps` | 0 | 44 | Set |
| `monitor` | 1 | 118 | Set |
| `mpf` | 0 | 18 | Set |
| `mrsno` | 1 | 123 | Set |
| `multi-user-beamformee` | 1 | — | — |
| `nan` | 1 | 6 | Set and clear |
| `nanho` | 0 | 64 | Clear |
| `nanrange` | 1 | — | — |
| `nap` | 0 | 68 | Set and clear |
| `ndoe` | 1 | 30 | Set |
| `obss_hw` | 0 | 101 | Set and clear |
| `ocl` | 0 | 47 | Set |
| `oct` | 0 | 98 | — |
| `ocv` | 0 | 107 | Set and clear |
| `ocv_ap` | 0 | 108 | Set and clear |
| `ops` | 0 | 56 | Set |
| `owe` | 0 | 96 | Set |
| `peerstats` | 0 | 104 | Set |
| `pfnx` | 1 | 36 | Set |
| `phy_cal_ecounter` | 1 | 99 | Set |
| `phy_ecounter` | 1 | 90 | Set |
| `pktfltr2` | 1 | 31 | Set |
| `pmr` | 1 | — | — |
| `proptxstatus` | 1 | — | — |
| `proxd` | 1 | 48 | Set |
| `prune_wpa` | 1 | — | — |
| `psbw` | 0 | 3 | Set |
| `ptm` | 0 | 91 | Set |
| `qos_mgmt` | 0 | 95 | — |
| `radio_pwrsave` | 1 | — | — |
| `rc1cx` | 0 | 85 | Set |
| `rc2cx` | 0 | 84 | Set |
| `rng_reseed` | 0 | 81 | — |
| `rsdb` | 1 | 46 | Set |
| `sae` | 1 | 65 | Set and clear |
| `sae-ap` | 1 | 75 | Set and clear |
| `sae_h2e` | 1 | 100 | Set |
| `sae_pk` | 0 | 109 | Set and clear |
| `sc` | 0 | 76 | Set |
| `scancache` | 1 | — | — |
| `scanmac` | 1 | 51 | Set |
| `scca` | 0 | 112 | Set and clear |
| `scr` | 1 | — | — |
| `sib` | 0 | 92 | — |
| `single-user-beamformee` | 1 | — | — |
| `single-user-beamformer` | 1 | — | — |
| `softapstats` | 0 | 122 | Set |
| `spmi` | 0 | 94 | — |
| `spmi_scan_fwd` | 0 | 117 | Set |
| `sta` | 1 | — | — |
| `tdmtx` | 1 | 4 | Set |
| `tko` | 1 | 49 | Set |
| `tsync` | 0 | 52 | Set |
| `tvpm` | 1 | 59 | Set |
| `tx-prof` | 1 | 78 | Set |
| `txcap` | 2 | — | — |
| `txcap3` | 1 | — | — |
| `txhist` | 0 | 69 | Set |
| `txpwrcache` | 1 | — | — |
| `ucm` | 1 | — | — |
| `ve` | 1 | 21 | Set |
| `vht-prop-rates` | 1 | — | — |
| `wds` | 1 | — | — |
| `wme` | 1 | — | — |
| `wnm` | 1 | 25 | Set |

## Bits outside the legacy word table

| Driver bit | Direct extended update | Verified consumer or separate legacy rule |
| ---: | --- | --- |
| 11 | Set and clear | Tethering blocker. The separate legacy `ap` check clears the blocker when that word is present. |
| 86 | Set | HP2P eligibility. The separate legacy `hp2p` check sets the bit when that word is present. |
| 105 | Set and clear | Beacon protection support check. |
| 106 | Set and clear | Checked with 105 before the driver configures beacon protection. Its independent meaning remains open. |
| 115 | Set | Read by multi-link status and 802.11be adapter initialization code in the shared driver. |
| 116 | Set | Read after an EHT check on the beacon in the shared driver. |
| 121 | Set | Controls a card-capability flag. Its feature name remains open. |

The exact consumer callsites are in the [extended feature evidence](../evidence/2026-11-17-extended-firmware-capabilities.json).
The [discovery catalog](capability-catalog.md) links the words, measurements and driver paths to their practical uses.
