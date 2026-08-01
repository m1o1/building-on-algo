// Package circuit defines the zero-knowledge circuit for the private
// governance vote described in Chapter 23 of Building on Algorand.
//
// The circuit proves: "I know a choice and a randomness such that
// MiMC(choice, randomness) = commitment AND choice < num_choices",
// without revealing either the choice or the randomness.
package circuit

import (
	"github.com/consensys/gnark/frontend"
	"github.com/consensys/gnark/std/hash/mimc"
)

// VoteCircuit is the constraint system for one ballot.
//
// Commitment and NumChoices are public: the on-chain verifier receives them as
// the public-input blob, and the governance contract binds them to its own
// state. Choice and Randomness are the witness and never leave the prover.
type VoteCircuit struct {
	// Public inputs (visible to the verifier)
	Commitment frontend.Variable `gnark:",public"`
	NumChoices frontend.Variable `gnark:",public"`

	// Private inputs (the witness --- known only to the prover)
	Choice     frontend.Variable
	Randomness frontend.Variable
}

// Define states the three constraints the proof must satisfy.
func (c *VoteCircuit) Define(api frontend.API) error {
	// Constraint 1: commitment = MiMC(choice, randomness).
	//
	// This is the same hash the AVM computes with
	// op.mimc(MiMCConfigurations.BN254Mp110, choice_bytes + randomness)
	// during reveal_vote, so the circuit and the contract agree on what a
	// commitment is.
	h, err := mimc.NewMiMC(api)
	if err != nil {
		return err
	}
	h.Write(c.Choice)
	h.Write(c.Randomness)
	api.AssertIsEqual(h.Sum(), c.Commitment)

	// Constraint 2: choice <= num_choices - 1, i.e. choice is a valid ballot.
	api.AssertIsLessOrEqual(c.Choice, api.Sub(c.NumChoices, 1))

	// Constraint 3: choice fits in 8 bits. Field elements have no sign, so
	// "choice >= 0" is not a statement that can be made; the useful bound is
	// that choice is small, which rules out the large field elements that
	// would otherwise satisfy constraint 2 by wrapping.
	bits := api.ToBinary(c.Choice, 8)
	api.AssertIsEqual(api.FromBinary(bits...), c.Choice)

	return nil
}
