\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# Mastery Checkpoint: Building a DEX {-}

**Build a quoter another contract can trust.** Deploy the AMM from Chapter 14. Then write a *separate* contract that reads that pool's reserves, quotes the output of a swap including the fee, and refuses to quote against a pool that did not come from the factory in Chapter 16.

This is the only checkpoint that builds on top of something you already have, and that is the point: the interesting part is not the arithmetic, it is trusting a contract you did not deploy. The provenance refusal is Chapter 17's Exercise 5 wearing a different consumer --- if you wrote that exercise, reuse your answer here.

It is accepted when:

- [ ] Your quote matches what the pool actually returns for the same input, exactly, for at least five different sizes including one that moves the price several percent
- [ ] Rounding never favours the caller
- [ ] A contract that answers the same ABI but was not created by the factory is rejected, and you have deployed one and watched it be rejected
- [ ] The quoter reads reserves without calling the pool, and you can say what that buys
- [ ] A quote for a size larger than the pool holds fails rather than returning nonsense

**Fallback:** skip the provenance check and quote against a pool id you pass in. You keep the pricing and composition work; write down what an attacker does with the version you shipped.

**If you cannot start:** Chapter 13 for the curve and the rounding, Chapter 15 for reading another application's state and for the id question the AVM will not answer, and Chapter 16 for the registry that makes provenance checkable at all.
