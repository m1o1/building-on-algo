\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# Mastery Checkpoint: Chance {-}

**Build a random assignment nobody can game.** N applicants stake for K slots --- seats in a cohort, plots in a garden, anything oversubscribed --- one beacon read picks the K winners, and every non-winner gets their stake back.

The drawing is the least of it. K distinct winners have to come out of one 32-byte value --- hash-chain the value, or store the seed in a global bytes slot and slice it; either way it is not one line --- and every actor still has a moment where cheating would pay. Chapter 18's Exercise 4 made you weigh the modulo bias in one draw; K draws multiply that question, and your derivation should say where you stand on it.

It is accepted when:

- [ ] Nobody --- including the operator --- can learn any winner before registration closes, and you can say what would break if they could
- [ ] The operator cannot re-run the assignment, and cannot decline to run it in a way that keeps the money
- [ ] An applicant who registers after the commitment is refused
- [ ] Registering twice does not improve an address's odds --- that is a property, not a mechanism, and you can name the mechanism you chose: refuse a second registration per address (Chapter 9's `not in` guard), or draw over distinct addresses
- [ ] The K winners are distinct, you can say how K indices came out of 32 bytes, and a losing applicant can recompute all K from public values
- [ ] Every non-winner recovers their stake exactly once --- and these refunds run *after* a successful draw, so Chapter 19's `drawn == 0` refund gate cannot be copied; working out what replaces it is this checkpoint's best transfer step
- [ ] Your contract reads the beacon through the method that lets it name its own error, and you can say what the other one costs a user
- [ ] It runs against a stub you control and against a real deployed beacon, with the same contract and one line different
- [ ] You have made the beacon go silent and watched everyone --- would-be winners included --- get their stake back

**Fallback:** fix the applicant list at creation and hold it in global state --- three 32-byte addresses fit beside a short key in one 128-byte slot, so a small N needs no boxes at all. The randomness and the refund discipline are unchanged.

**If you cannot start:** Chapter 18 for the draw and the commitment, Chapter 5 for the applicant records, Chapter 11 for who is billed for them.
