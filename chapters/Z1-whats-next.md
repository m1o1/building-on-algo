\newpage

# What's Next {-}

Look at what you have accomplished. You started with no smart contract knowledge and built a token vesting system with safe integer math and box storage, extended it with NFTs for transferable financial rights, constructed a constant product AMM with LP token mechanics, designed a hybrid stateful/stateless limit order book with keeper bots, and pushed the AVM to its limits with zero-knowledge proofs for private voting. Along the way, you internalized the security patterns that prevent real exploits, the MBR lifecycle that keeps contracts solvent, and the atomic group composition that makes DeFi composable. These are not toy examples --- they are the building blocks of production protocols.

Here is where to go next.

**Concentrated liquidity AMMs.** The constant product AMM in Chapter 5 is the Uniswap V2 model. The broader DeFi industry has moved toward concentrated liquidity (V3), where LPs choose price ranges for dramatically higher capital efficiency. No Algorand DEX has yet implemented a full V3-style concentrated liquidity AMM --- this is an open opportunity. Porting V3 concepts to the AVM would require creative use of box storage for tick data and careful opcode budget management for tick-crossing math.

**Lending and borrowing protocols.** Folks Finance and the now-sunset Algofi demonstrated that full lending/borrowing is possible on Algorand. Key concepts to study: overcollateralization, health factors, liquidation mechanics (calling AMM swaps via inner transactions to convert seized collateral), and interest rate models (utilization curves). These protocols compose heavily with AMMs for price oracles and liquidation execution.

**Cross-chain bridges and State Proofs.** Chapter 9 introduced State Proofs and Falcon signatures. The practical application: building a light client on Ethereum that verifies Algorand State Proofs, enabling trustless asset transfers between chains. This is active infrastructure work in the Algorand ecosystem.

**Ecosystem integration.** This book built everything from scratch. Production applications integrate with existing protocols. Study the ABIs of Tinyman, Pact, and Folks Finance to understand how to call their contracts from yours. The ARC-56 specs for deployed contracts are your entry point --- load them with AlgoKit Utils and call methods directly.

**Off-chain infrastructure.** Production DeFi needs indexer services, event-driven backends, keeper bots, and monitoring. The Algorand Indexer REST API, Conduit data pipeline, and Nodely public endpoints provide the building blocks. Start with a Python service that watches for swap events (by parsing ARC-28 logs) and updates a price feed.

**MainNet operations.** LocalNet and TestNet are training wheels. MainNet deployment requires: key management (hardware wallets or HSMs, never KMD), contract verification (proving source matches deployed bytecode), monitoring and alerting, and an emergency response plan for what to do when you find a bug in an immutable contract (answer: communicate immediately, recommend users withdraw, deploy V2).

**Consensus participation and staking rewards.** Since the end of governance period 14 (Q1 2025), Algorand rewards come from consensus participation rather than quarterly governance commitments. Validators earn 10 Algo per proposed block (decaying over time) plus 50% of transaction fees. Participation requires running a node with at least 30,000 Algo staked and registering participation keys with a 2-Algo fee. This is Algorand's long-term economic model --- understanding it matters if you are building protocols that interact with staking (like Folks Finance's liquid staking) or if you plan to operate your own infrastructure.

**Contract migration.** Immutable contracts cannot be patched, but they can be superseded. When Tinyman migrated from V1 to V2 after the exploit, the process was: deploy V2, publicly announce a migration deadline, build a migration UI that withdraws liquidity from V1 and deposits into V2 in a single atomic group, and eventually shut down the V1 frontend while leaving the V1 contracts on-chain for anyone who still needs to withdraw. The key principle: the old contract remains functional for withdrawals indefinitely (it is immutable, after all), but new deposits are directed exclusively to V2. Plan your state schema so that migration-critical data (user balances, LP positions) can be read by the new contract via `app_global_get_ex` or reconstructed from on-chain history via the indexer.
