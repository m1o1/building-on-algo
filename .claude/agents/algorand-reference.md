---
name: algorand-reference
description: "NOT AN AGENT -- DO NOT SPAWN. A knowledge-base document that agents READ. Bulk Algorand reference data that is NOT review material: node hardware sizing, API service endpoints, the Indexer PostgreSQL schema, Conduit pipeline requirements, catchpoints, node config warnings, the Known Addresses Registry, and Algorand governance history. Split out of algorand-expert so that file stays readable in one pass. Read this ONLY when a task is genuinely about node operations, Indexer queries, resolving a MainNet address, or governance history -- never for a chapter review."
---

# Algorand Reference Data (Operational, Not Review Material)

This file was split out of `.claude/agents/algorand-expert.md` because none of it
has ever settled a book review, and carrying it there made that file too large to
read in a single pass -- one paginated Read of it hard-failed a 25,000-token cap.

**The precedence rules of `algorand-expert.md` apply here unchanged:** official
documentation beats source, source beats compile tests, compile tests beat memory,
and later dated entries beat earlier ones. Addresses, endpoints and hardware figures
drift; anything here that is going into the book must be re-verified against its
cited source on the day it is used, not trusted because it is written down.

---

## Node Operations and Infrastructure

### Node Hardware Requirements

| Type | vCPU | RAM | Storage | Bandwidth |
|------|------|-----|---------|-----------|
| Validator | 8 | 16 GB | 100 GB NVMe | 100 Mbps, <100ms latency |
| API Provider | 8 | 16 GB | 100 GB NVMe | 100 Mbps |
| Archiver | 8 | 16 GB | 3 TB SSD + 100 GB NVMe | High |
| Repeater (Relay) | 8+ | 16 GB | 3.1 TB | High (always archival) |

Source: [dev.algorand.co/nodes/types/](https://dev.algorand.co/nodes/types/)

### API Services Quick Reference

| Service | Default Port | Auth Header | Token File |
|---------|-------------|-------------|-----------|
| algod | 4001 | `X-Algo-API-Token` | `algod.token` |
| Indexer | 8980 | `X-Indexer-API-Token` | -- |
| KMD | 4002 | `X-KMD-API-Token` | `kmd-version/kmd.token` |

### Nodely (Free Public API) Endpoints

| Network | algod | Indexer |
|---------|-------|---------|
| MainNet | `https://mainnet-api.4160.nodely.dev` | `https://mainnet-idx.4160.nodely.dev` |
| TestNet | `https://testnet-api.4160.nodely.dev` | `https://testnet-idx.4160.nodely.dev` |
| BetaNet | `https://betanet-api.4160.nodely.dev` | `https://betanet-idx.4160.nodely.dev` |

Free tier uses empty string `""` as API token. Source: [nodely.io/docs/free/endpoints/](https://nodely.io/docs/free/endpoints/)

### Indexer PostgreSQL Schema (from github.com/algorand/indexer migration files)

| Table | Key Columns | Notes |
|-------|-------------|-------|
| `txn` | `round`, `intra`, `typeenum`, `asset`, `txid`, `txn` (jsonb), `extra`, `closed_at` | `txn` is jsonb (NOT msgpack) |
| `account` | `addr`, `microalgos`, `rewardsbase`, `rewards_total`, `deleted`, `created_at`, `closed_at`, `keytype`, `account_data` | |
| `account_asset` | `addr`, `assetid`, `amount`, `frozen`, `deleted`, `created_at`, `closed_at` | |
| `asset` | `index`, `creator_addr`, `params` (jsonb), `deleted`, `created_at`, `closed_at` | |
| `app` | `index`, `creator`, `params` (jsonb), `deleted`, `created_at`, `closed_at` | |
| `account_app` | `addr`, `app`, `localstate` (jsonb), `deleted`, `created_at`, `closed_at` | |

Additional tables: `block_header`, `txn_participation`, `metastate`, `app_box`.

### Conduit Pipeline Requirements

- 4 CPU cores, 8 GB RAM, 40 GiB storage, 3000 IOPS (for algod follower node)
- Architecture: Follower node -> Conduit importer -> optional processors -> PostgreSQL exporter
- Configured via `conduit.yml`

Source: [github.com/algorand/conduit README](https://github.com/algorand/conduit)

### Catchpoint Fast Catchup URL

```
https://algorand-catchpoints.s3.us-east-2.amazonaws.com/channel/mainnet/latest.catchpoint
```

### Node config.json Warning

Never enable `IsIndexerActive` -- this activates the deprecated V1 indexer with severe performance impact. The V2 indexer runs as an independent process (Conduit).

---

## Known Addresses Registry

Sources: [Algorand Foundation Transparency](https://algorand.co/algorand-foundation/transparency), [go-algorand genesis.json](https://github.com/algorand/go-algorand/blob/master/installer/genesis/mainnet/genesis.json), [Folks Finance SDK](https://github.com/Folks-Finance/algorand-js-sdk), on-chain verification via Nodely API.

### Protocol Special Addresses

| Address | Label | Source |
|---------|-------|--------|
| `Y76M3MSY6DKBRHBL7C3NNDXGS5IIMQVQVUAB6MP4XEMMGVF2QWNPL226CA` | Fee Sink (MainNet) | genesis.json |
| `737777777777777777777777777777777777777777777777777UFEJ2CI` | Rewards Pool (MainNet) | genesis.json |
| `A7NMWS3NT3IUDMLVO26ULGXGIIOUQ3ND2TXSER6EBGRZNOBOUIQXHIBGDE` | Fee Sink (TestNet) | genesis.json |
| `7777777777777777777777777777777777777777777777777774MSJUVU` | Rewards Pool (TestNet) | genesis.json |

### Algorand Foundation Governance Rewards (per-period payout addresses)

| Address | Label | Source |
|---------|-------|--------|
| `GULDQIEZ2CUPBSHKXRWUW7X3LCYL44AI5GGSHHOQDGKJAZ2OANZJ43S72U` | AF Governance Rewards (generic/early periods) | On-chain, community sources |
| `2K24MUDRJPOOZBUTE5WW44WCZZUPVWNYWVWG4Z2Z2ZZVCYJPVDWRVHVJEQ` | AF Governance Rewards (Period 11) | AF Transparency |
| `5GPWAOJJC45WCM5QBMRW5F53MTDVAFJDIDNF2YMTI7EN5YUQMLFJLKSKUM` | AF Governance Rewards (Period 12) | AF Transparency |
| `E53AV44SU2UFR3SD6EW3KEVXMPC4HFNRYSDXYNKKYNPPC63ID7USKWCKXI` | AF Governance Rewards (Period 13) | AF Transparency |
| `DLG5EP7UMPHQNA7Z4IEO6GTIDSN6WG4HUUXBJ72E7PTP2NXIOLGNS4DNKI` | AF Governance Rewards (Period 14) | AF Transparency |

Note: Period 10 address (`75X4V7CEN6HW3EYSJEJLWDNVX3BOJPPEHU2S34FSEKIN5WEB2OZN2VL5T4`) exists on-chain but could not be verified from current AF Transparency page.

### Algorand Foundation xGov (verified from AF Transparency page)

| Address | Label |
|---------|-------|
| `DRWUX3L5EW7NAYCFL3NWGDXX4YC6Y6NR2XVYIC6UNOZUUU2ERQEAJHOH4M` | AF xGov Term Pool 1 |
| `PN4J5F5HRMQ7VAHRQWQ3G52T25KAUMPKUDU7B2GWFNLI3ZDU4W4DQITPIA` | AF xGov Term Pool 2 |
| `BU3I4ASYTQULW5KWMNCBMF6NQSSC6WM52KRUQEVVH4WQP2VHDKUKHR2W5Q` | AF xGov Term Pool 3 |
| `OHYAQI5UJAY77R4TIZZVYPNNKVYEHHI36QUIU3NUKPMIZJAQKDRFC77XMM` | AF xGov Term Pool 4 |
| `3KWWDTQLXPKUPL3W4M4VVAE3VITOYIRCDT5Z2RRHNJE5KY3CTYMV6J2LF4` | AF xGov Payments |
| `NSIVDOYUJCIYYC33XJABCZZNARSU6J6ZC5DPUOWIIFQQY4IIZIJTTEE4NY` | AF Term Pool Payments |

### Algorand Foundation Market Operations (verified from AF Transparency page)

| Address | Label |
|---------|-------|
| `37VPAD3CK7CDHRE4U3J75IE4HLFN5ZWVKJ52YFNBX753NNDN6PUP2N7YKI` | AF Market Operations (BitGo) |
| `44GWRTQGSAYUJJCQ3GFINYKZXMBDVKCF75VMCXKORN7ZJ6BKPNG2RMGH7E` | AF Market Operations (Fireblocks) |

### Folks Finance (verified from Folks Finance SDK and on-chain)

| Identifier | Value | Source |
|------------|-------|--------|
| gALGO ASA ID | 793124631 | [Folks Finance SDK](https://github.com/Folks-Finance/algorand-js-sdk/blob/main/src/algo-liquid-governance/common/mainnet-constants.ts) |
| fALGO ASA ID | 971381860 | [Folks Finance SDK](https://github.com/Folks-Finance/algorand-js-sdk/blob/main/src/lend/constants/mainnet-constants.ts) |
| fgALGO ASA ID | 971383839 | Folks Finance SDK |
| gALGO Mint/Redeem Contract | `GGP73AZM3CMLDLXUDVR2NIULL3M7SORSI4N7DFIOZTVL62UOVSQUTZYEA4` | On-chain creator of ASA 793124631 |
| Governance Signal (vanity) | `FOLKSGOVERNANCEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEH4K6TMY` | On-chain |
| ALGO Deposit Pool app | 971368268 | Folks Finance SDK |
| Governance Deposit Pool app | 971370097 | Folks Finance SDK |
| Loan Type GENERAL | 971388781 | Folks Finance SDK |
| Loan Type ALGO_EFFICIENCY | 971389489 | Folks Finance SDK |

**Folks Finance Governance App IDs (V2):**

| Period | App ID | Source |
|--------|--------|--------|
| G7 | 1073098885 | [Folks Finance SDK](https://github.com/Folks-Finance/algorand-js-sdk/blob/main/src/algo-liquid-governance/v2/constants/mainnet-constants.ts) |
| G8 | 1136393919 | Folks Finance SDK |
| G9 | 1200551652 | Folks Finance SDK |
| G10 | 1282254855 | Folks Finance SDK |
| G11 | 1702641473 | Folks Finance SDK |
| G12 | 2057814942 | Folks Finance SDK |
| G13 | 2330032485 | Folks Finance SDK |
| G14 | 2629511242 | Folks Finance SDK |

**Pool Returns Distributors** (verified on-chain only -- not in Folks Finance docs):
- `LWUWBZPVBS24TDBDZ72LUYJJF75KUJ3IUP6YGG45PVKGNAJYRGQD5CSCPA`
- `UXVAPU4KERSMNUILDVZUKKF4KMWQ7RFSSYPXYSEGSYNYILC4FEHISKRBNM`
- `27D6WYEDJZHLFCLJNDJF63RFYFO32KZHOYBHET7BSVDHSTJQQI5GFN2QVI`
- `MQOZTXRBYZ6JIPGQLNV6Y4REHFKVZKBXKIJVOGEYUDPLQNYZ5YJP72XZOE`

### AlgoFi (Historical -- shut down July 2023)

| Identifier | Value | Source |
|------------|-------|--------|
| vALGO (AF-BANK-ALGO-VAULT) ASA ID | 879951266 | On-chain |
| Vault app (primary) | 879935316 | [AlgoFi docs (archived)](https://web.archive.org/web/20220926054019/https://docs.algofi.org/vault/mainnet-contracts) |
| Vault app (secondary) | 900932886 | On-chain |

---

## Algorand Governance Historical Reference

Governance ran for 14 quarterly periods (Q4 2021 -- Q1 2025), then replaced by consensus staking. Sources: [Algorand Governance API](https://governance.algorand.foundation/api/periods/), [Algorand Foundation blog](https://algorand.co/blog/governance-rewards-its-a-wrap-reflecting-and-what-comes-next), [af-gov1-spec.md](https://github.com/algorandfoundation/governance/blob/main/af-gov1-spec.md).

**Cumulative**: 33.9 billion ALGO committed across 14 periods, averaging ~2.4B/period, peaking ~3.8B.

### Governance Mechanics

- **Committing**: Zero-amount payment to governance address with note `af/gov1:j{"com":AMOUNT,...}`. Optional fields: `bnf` (beneficiary), `xGv` (xGov delegation). ALGO does NOT leave the wallet.
- **Voting**: Zero-amount payment with note `af/gov1:j[SESSION_IDX,"a","b",...]` (first element is voting session index, NOT governance period number).
- **Two contracts**: Rewards Application Contract (stateful) + Stateless Governance Escrow, audited by Runtime Verification.
- **Reward formula**: `Governor_Reward = REWARD_POOL * (Governor_Committed / Total_Committed)`

Source: [af-gov1-spec.md](https://github.com/algorandfoundation/governance/blob/main/af-gov1-spec.md), [Runtime Verification audit](https://runtimeverification.com/blog/runtime-verification-audits-the-rewards-contracts-of-algorand-s-community-governance)

### Period-by-Period Summary

| Period | Dates | Reward Pool | Key Events |
|--------|-------|-------------|------------|
| GP1 | Oct-Dec 2021 | 60M ALGO | Launch. ~50K governors, ~1.71B committed. Option A vs B vote (A won 56.6%, no slashing). ~14% APR |
| GP2 | Jan-Mar 2022 | 70.5M ALGO | 95% voted to create xGov tier. ~37.2K governors, ~2.81B committed |
| GP3 | Apr-Jun 2022 | 70.5M ALGO | Folks Finance V1 liquid governance (period-specific gALGO tokens, 5% fee on rewards) |
| GP4 | Jul-Sep 2022 | 70.5M ALGO | 66% voted for 7M DeFi rewards allocation. LP token governance introduced |
| GP5 | Oct-Dec 2022 | 70.5M total (7M DeFi) | Folks Finance V2 (single continuous gALGO, no fee). AlgoFi vault launched |
| GP6 | Jan-Mar 2023 | ~70M total | DeFi rewards expanded. Protocol-direct distribution (TDR) added |
| GP7 | Apr-Jun 2023 | ~56M total (16M DeFi) | xGov pilot launched (ARC-33/ARC-34) |
| GP8 | Jul-Sep 2023 | 42M (24.5M gen + 17.5M DeFi) | AlgoFi announced shutdown (July 2023). Ultrastaking introduced |
| GP9 | Oct-Dec 2023 | 32M (17.5M gen + 14.5M DeFi) | Escrow accounts begin running consensus nodes |
| GP10-12 | 2024 | ~22-32M | Mature governance with Folks Finance escrow + node participation |
| GP13 | Oct-Dec 2024 | Declining | xGov council election measures |
| GP14 | Jan-Mar 2025 | 20M (10M gen + 10M DeFi) | FINAL governance period. "The Last Dance" |

### Folks Finance Liquid Governance

- **gALGO** (ASA 793124631): Liquid governance receipt token
- **V1** (GP3-GP4): Period-specific tokens (gALGO3, gALGO4). 5% fee on governance rewards.
- **V2** (GP5+): Single continuous gALGO across all periods. Fees removed. Revenue from early-claim spread.
- **Minting**: 1:1 ratio (mint X ALGO, receive X gALGO)
- **Redemption**: Exactly 1:1 at period end (burn X gALGO, receive X ALGO)
- **Rewards**: NOT bundled with redemption -- paid separately. Based on amount minted, not current holdings.
- **Escrow Architecture**: Dedicated escrow per user, controlled by LogicSig, rekeyed to period-specific governance address each period. Escrows can register participation keys.

Source: [Folks Finance V2 announcement](https://folksfinance.medium.com/algo-liquid-governance-2-0-2911baba9269), [Folks Finance V1 docs](https://v1.docs.folks.finance/protocol-architecture/overview/algo-liquid-governance)

### Ultrastaking (Leveraged Governance)

Amplifies governance rewards by borrowing ALGO against gALGO collateral (up to ~4x leverage):

1. Deposit ALGO -> receive gALGO
2. Deposit gALGO as collateral (mints fgALGO, ASA 971383839)
3. Borrow more ALGO against collateral
4. Commit total ALGO to governance
5. Profit = governance rewards on leveraged amount - borrow interest

Period transitions use flash loans to atomically roll loans between periods in a single 16-transaction group.

### xGov (Expert Governance)

- **Launched GP7** via ARC-33/ARC-34. Source: [ARC-33](https://github.com/algorandfoundation/ARCs/blob/main/ARCs/arc-0033.md)
- Governors opted in by directing governance **rewards** (not principal) to xGov Term Pool for 12 months
- **Voting power**: 1 ALGO of committed rewards = 1 vote
- **Penalty**: Must use all available votes each session or forfeit deposited rewards
- **Post-GP14 reimagination**: Tied to consensus participation. Each proposed block = 1 xGov vote. No minimum ALGO requirement for xGov itself (30K minimum applies only to staking rewards eligibility). Focus shifted to retroactive grants for open-source builders.

Source: [Algorand Forum xGov Beta Guide](https://forum.algorand.co/t/xgov-beta-enrolling-as-an-xgov-and-voting-on-proposals/14808)

### Key Difference: Governance vs Consensus Staking

Governance (GP1-GP14): Quarterly commitment + voting -> rewards. No lockup but balance must stay above commitment. Ended Q1 2025.

Consensus Staking (Algorand 4.0, January 2025): Rewards for running nodes and proposing blocks. ~10 ALGO/block (decaying 1% per million blocks). 50% of transaction fees to proposer. No lockup, fully liquid. Folks Finance transitioned from gALGO to **xALGO** for the new model.

Source: [Algorand Staking Rewards FAQ](https://algorand.co/staking-rewards-faq)
