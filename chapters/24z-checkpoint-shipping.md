\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# Mastery Checkpoint: Shipping {-}

**Take something you have already built and make it operable.** Any contract from this book or from the checkpoints above. The build is not the work here; the work is everything that has to be true before you would let somebody else depend on it.

It is accepted when:

- [ ] Every state-changing method emits an event, and you have found one of those events by its four-byte prefix rather than by reading state
- [ ] Every assertion carries a code, and a client with no source map can tell which one failed
- [ ] There is an update path, it is gated, and it can be closed permanently
- [ ] You have frozen it and confirmed the update path is gone
- [ ] A counterparty can check the code has not changed since you froze it, without trusting you
- [ ] The contract can be shut down and its account emptied, and the balance afterwards is zero
- [ ] Deleting it while storage remains is refused rather than allowed

**Fallback:** the freeze and the shutdown are the two that cannot be added later. If you do one thing here, do those.

**If you cannot start:** Chapter 24 for the three additions --- the event, the error code, the lifecycle stance; Chapter 10 for the switch the pause is built on; Chapter 11 for who holds the balance the shutdown recovers; Chapter 5 for why the boxes have to go before the account can close.
