\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# Mastery Checkpoint: Cryptography {-}

**Build a sealed-bid auction you can afford to run.** Bidders commit to a bid by submitting a hash. After a deadline they reveal the bid and the nonce, the contract checks the commitment, and the highest valid revealed bid wins.

Then price it. The second half is the checkpoint: say what a reveal costs in opcodes, and how many reveals fit in one transaction and in one group.

It is accepted when:

- [ ] A reveal whose nonce does not match the commitment is rejected
- [ ] A reveal after the deadline is rejected, and a commit after the deadline is too
- [ ] A bidder cannot change their commitment once made
- [ ] Your opcode figure is measured against a run, not estimated from a table
- [ ] You can say what a bidder learns about other bids before the reveal, and whether that is what you intended
- [ ] You can say what happens to a bidder who never reveals, and defend the choice
- [ ] You can price the private upgrade: a range proof in place of the reveal --- "my bid is valid, and I am not showing it" --- costs a verification group, and you can say how many transactions per bid, using Chapter 23's group arithmetic

**Fallback:** fix the field of bidders at creation and hold commitments in global state. The cost model is unchanged and the storage arithmetic goes away.

**If you cannot start:** Chapter 18 for the commitment, Chapter 22 for what each hash costs, Chapter 11 for the budget and how it pools.
