\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# Mastery Checkpoint: Value Under Management {-}

**Build a role-gated escrow that pays for itself.** A depositor locks Algo against a named beneficiary. An arbiter, a third address set at creation, either releases the deposit to the beneficiary or refunds it. Nobody else can do anything.

It is accepted when:

- [ ] Every method that moves value has an explicit check on who called it, and you can name the check for each
- [ ] A stranger calling any privileged method fails, and you have a test that proves it rather than an argument that it would
- [ ] The contract's own balance is the same before and after a release, apart from the deposit --- it pays no fee out of its own funds
- [ ] A readonly method reports the contract's current minimum balance and what is making it up
- [ ] Depositing when the contract cannot afford the record fails at deposit time, not later
- [ ] The arbiter cannot pay themselves

**Fallback:** drop the arbiter and let the depositor cancel before a deadline. You keep the authorization work and lose one role.

**If you cannot start:** Chapter 10 for what `Txn.sender` does and does not prove, Chapter 11 for who is billed and who pays the fees.
