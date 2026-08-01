\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# Mastery Checkpoint: Stateless Programs {-}

**Build a one-shot delegated top-up.** A user signs a program that lets a keeper pull exactly one payment out of their account --- a fixed amount, to a fixed receiver, before a fixed round --- without the keeper ever holding their key.

Then attack it. This checkpoint is half construction and half adversary work, and the second half is the one that matters.

It is accepted when:

- [ ] `close_remainder_to`, `asset_close_to` and `rekey_to` are each pinned, and you can say what an attacker does with each one you leave open --- or, for one of the three, why no attacker ever could
- [ ] The fee is capped, and the cap is not the network minimum
- [ ] The program expires
- [ ] The amount and the receiver are fixed by the program, not supplied by the caller
- [ ] "Once" is actually enforced, and you can state the mechanism --- a program alone cannot count
- [ ] Five of the six guards above you have attacked: removed the guard, written the transaction that exploits its absence, run it on LocalNet, and recorded what it took. The sixth --- `asset_close_to`, on a payment-only delegation --- you check off by proving the exploit cannot occur: the protocol rejects a payment carrying that field as malformed before any program runs. Five you exploit, one you prove impossible

**Fallback:** drop the one-shot requirement and ship an expiring allowance instead. Do not drop the adversary half; it is the checkpoint.

**If you cannot start:** Chapter 20, from two directions. Its four programs with one hole each are this checkpoint turned around --- there you found the holes, here you write the program and the attack. And its Exercise 5 is the construction half: "at most once, ever" is exactly the mechanism this task makes you state.
