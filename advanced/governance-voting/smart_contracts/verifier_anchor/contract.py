import typing

from algopy import ARC4Contract, arc4

Bytes32: typing.TypeAlias = arc4.StaticArray[arc4.Byte, typing.Literal[32]]


class VerifierAnchor(ARC4Contract):
    """The transaction the AlgoPlonk verifier LogicSig signs.

    A LogicSig has no state and cannot be called; it authorises a transaction.
    The generated verifier reads the proof from `Txn.application_args(1)` and
    the public inputs from `Txn.application_args(2)`, so the transaction it
    signs has to be an application call with three arguments --- and something
    has to be at the other end of it. This contract is that something.

    `verify` deliberately checks nothing. All the verification happens in the
    LogicSig before this program is ever reached: if the proof does not verify,
    the LogicSig rejects, the transaction is never authorised, and the group
    fails. What the app call provides is a place for the proof and the public
    inputs to sit as transaction fields, where a *second* contract --- the
    governance app at the end of the group --- can read them and bind them to
    its own state. That reader is `GovernanceVoting.record_bound_proof`.

    So the anchor must not be mistaken for the check. An app call to this
    contract that is signed by an ordinary key rather than by the verifier
    LogicSig proves nothing at all, which is exactly why the governance app
    compares the sender against a stored address instead of trusting that a
    call to this app happened.
    """

    @arc4.abimethod
    def verify(
        self,
        proof: arc4.DynamicArray[Bytes32],
        public_inputs: arc4.DynamicArray[Bytes32],
    ) -> arc4.Bool:
        return arc4.Bool(True)
