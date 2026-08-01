\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# Mastery Checkpoint: Foundations {-}

Each chapter closed with five claims you should be able to make. Those checked that you followed the chapter. This checks something else: whether you can build a thing the Part did not show you.

There is one of these checkpoints at the end of every Part, and each is a small program with a stated acceptance test. None of them is any of the artifacts in the book, and none needs a mechanism from a later Part. If a checkpoint is out of reach, the Part is not finished, whatever the individual chapter checklists said. The fastest repair is to reread the one chapter the acceptance criteria keep pointing at.

Every checkpoint carries a **fallback**. Take it rather than stopping: a smaller version finished teaches more than a full version abandoned.

**Build a subscription meter.** An account pays a fixed monthly fee to your contract. The contract records what each subscriber has paid through, answers whether a given address is currently subscribed, and lets the owner sweep the collected fees out.

Four methods is enough: `subscribe()` taking a payment, `paid_through(address)` as a read, `is_active(address)` as a read, and `sweep()` for the owner.

It is accepted when:

- [ ] A payment of less than the fee is rejected, and the rejection names why
- [ ] Paying twice extends the subscription rather than replacing it
- [ ] The contract never lets its balance fall below what its own storage requires, and refuses a subscription it cannot afford to record
- [ ] `is_active` uses the clock the contract can actually trust, and you can say why the other three candidates are wrong
- [ ] Nobody but the owner can call `sweep`
- [ ] There is a test that fails if you swap the comparison in `is_active`
- [ ] It deploys to LocalNet and all four methods work from a client

**Fallback:** hold subscribers in local state instead of boxes, which caps you at whoever opts in and removes the minimum-balance arithmetic. The rest of the checkpoint is unchanged.

**If you cannot start:** Chapter 3 for the two reads and what `readonly` does and does not promise, Chapter 4 for where the record lives, Chapter 5 for what one costs the contract to keep, Chapter 6 for the clock, Chapter 7 for taking the payment and sending the sweep, Chapter 8 for the test that would go red.
