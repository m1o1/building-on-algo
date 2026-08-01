// Command prove generates one ballot proof against the artifacts that
// gen-verifier produced, and prints everything the Python client needs.
//
// It does three things the Python side cannot do for itself:
//
//   - computes the MiMC commitment with gnark-crypto, which is the same
//     implementation the AVM's mimc opcode uses, so the commitment the voter
//     submits is the one reveal_vote will recompute on chain;
//   - produces a PLONK proof that the committed choice is in range, without
//     revealing it;
//   - writes the proof and public inputs in the binary layout AlgoPlonk's
//     generated LogicSig expects.
//
// Usage, from the zk/ directory:
//
//	go run ./cmd/prove -choice 1 -num-choices 3
//	go run ./cmd/prove -choice 1 -num-choices 3 -randomness <64 hex chars>
//
// With no -randomness it draws 32 random bytes and reduces them into the BN254
// scalar field, then prints what it used. Keep that value: it is half of the
// preimage the voter must present at reveal time.
package main

import (
	"bufio"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"math/big"
	"os"
	"path/filepath"

	"github.com/consensys/gnark-crypto/ecc"
	"github.com/consensys/gnark-crypto/ecc/bn254/fr"
	"github.com/consensys/gnark-crypto/ecc/bn254/fr/mimc"
	"github.com/consensys/gnark/backend/plonk"

	ap "github.com/giuliop/algoplonk"

	"zk-voting/circuit"
)

const generatedDir = "generated"

func main() {
	choice := flag.Uint64("choice", 0, "the ballot choice to prove (kept secret)")
	numChoices := flag.Uint64("num-choices", 3, "the election's choice count")
	randomHex := flag.String("randomness", "", "32-byte blinding factor, hex; random if empty")
	outPrefix := flag.String("out", "vote", "basename for the written proof files")
	flag.Parse()

	if err := run(*choice, *numChoices, *randomHex, *outPrefix); err != nil {
		fmt.Fprintln(os.Stderr, "prove:", err)
		os.Exit(1)
	}
}

func run(choice, numChoices uint64, randomHex, outPrefix string) error {
	if numChoices == 0 {
		return fmt.Errorf("-num-choices must be at least 1")
	}
	if choice >= numChoices {
		return fmt.Errorf("choice %d is not in range [0, %d)", choice, numChoices)
	}

	randomness, err := blindingFactor(randomHex)
	if err != nil {
		return err
	}

	// The commitment. gnark-crypto's bn254/fr/mimc is the implementation
	// behind the AVM's mimc opcode under MiMCConfigurations.BN254Mp110, and it
	// is what gnark's in-circuit mimc gadget is specified to agree with, so
	// this one value is what ties the circuit, the client and reveal_vote
	// together.
	commitment := mimcCommitment(choice, randomness)

	// Load what gen-verifier wrote rather than re-running the setup, so the
	// proof is provably against the committed proving key.
	ccs := plonk.NewCS(ecc.BN254)
	if err := readArtifact(filepath.Join(generatedDir, "vote_circuit.ccs"), ccs); err != nil {
		return err
	}
	pk := plonk.NewProvingKey(ecc.BN254)
	if err := readArtifact(filepath.Join(generatedDir, "vote_circuit.pk"), pk); err != nil {
		return err
	}
	vk := plonk.NewVerifyingKey(ecc.BN254)
	if err := readArtifact(filepath.Join(generatedDir, "vote_circuit.vk"), vk); err != nil {
		return err
	}

	compiled := &ap.CompiledCircuit{Ccs: ccs, Pk: pk, Vk: vk, Curve: ecc.BN254}

	assignment := circuit.VoteCircuit{
		Commitment: new(big.Int).SetBytes(commitment[:]),
		NumChoices: numChoices,
		Choice:     choice,
		Randomness: new(big.Int).Set(randomness),
	}

	// Verify() proves and then verifies off-chain. A proof that does not
	// verify here will not verify on chain either, and failing in Go is much
	// cheaper to read than failing inside a LogicSig.
	verified, err := compiled.Verify(&assignment)
	if err != nil {
		return fmt.Errorf("prove/verify: %w", err)
	}

	proofPath := filepath.Join(generatedDir, outPrefix+".proof")
	inputsPath := filepath.Join(generatedDir, outPrefix+".public_inputs")
	if err := verified.ExportProofAndPublicInputs(proofPath, inputsPath); err != nil {
		return err
	}

	var randBytes [32]byte
	randomness.FillBytes(randBytes[:])

	// The manifest is what the Python client reads. Everything in it is
	// public except `randomness` and `choice`, which are in the file only
	// because this is a single-machine demonstration; a real voter keeps them
	// off the wire until reveal.
	manifest := map[string]any{
		"choice":       choice,
		"num_choices":  numChoices,
		"randomness":   hex.EncodeToString(randBytes[:]),
		"commitment":   hex.EncodeToString(commitment[:]),
		"proof_file":   filepath.Base(proofPath),
		"inputs_file":  filepath.Base(inputsPath),
		"curve":        "BN254",
		"proof_system": "PLONK",
		"setup":        "PerpetualPowersOfTauBN254",
	}
	manifestPath := filepath.Join(generatedDir, outPrefix+".json")
	blob, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(manifestPath, append(blob, '\n'), 0o644); err != nil {
		return err
	}

	fmt.Printf("choice (secret):  %d\n", choice)
	fmt.Printf("randomness:       %s\n", hex.EncodeToString(randBytes[:]))
	fmt.Printf("commitment:       %s\n", hex.EncodeToString(commitment[:]))
	fmt.Printf("wrote %s, %s, %s\n", proofPath, inputsPath, manifestPath)
	return nil
}

// mimcCommitment hashes the two field elements the circuit hashes, in the same
// order: the choice zero-padded to 32 bytes, then the randomness.
func mimcCommitment(choice uint64, randomness *big.Int) [32]byte {
	h := mimc.NewMiMC()

	var choiceBytes [32]byte
	new(big.Int).SetUint64(choice).FillBytes(choiceBytes[:])
	h.Write(choiceBytes[:])

	var randBytes [32]byte
	randomness.FillBytes(randBytes[:])
	h.Write(randBytes[:])

	var out [32]byte
	copy(out[:], h.Sum(nil))
	return out
}

// blindingFactor parses -randomness, or draws one. Either way the result is a
// canonical BN254 scalar: the AVM's mimc opcode rejects a 32-byte block that is
// not a valid fr.Element encoding, so a raw 32 random bytes is not safe to use
// unreduced.
func blindingFactor(randomHex string) (*big.Int, error) {
	if randomHex == "" {
		var e fr.Element
		if _, err := e.SetRandom(); err != nil {
			return nil, fmt.Errorf("draw randomness: %w", err)
		}
		bv := new(big.Int)
		e.BigInt(bv)
		return bv, nil
	}

	raw, err := hex.DecodeString(randomHex)
	if err != nil {
		return nil, fmt.Errorf("-randomness is not hex: %w", err)
	}
	if len(raw) != 32 {
		return nil, fmt.Errorf("-randomness must be 32 bytes, got %d", len(raw))
	}
	bv := new(big.Int).SetBytes(raw)
	if bv.Cmp(fr.Modulus()) >= 0 {
		return nil, fmt.Errorf("-randomness is not below the BN254 scalar modulus")
	}
	return bv, nil
}

func readArtifact(path string, into io.ReaderFrom) error {
	f, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("%s: %w (run `go run ./cmd/gen-verifier` first)", path, err)
	}
	defer f.Close()

	if _, err := into.ReadFrom(bufio.NewReader(f)); err != nil {
		return fmt.Errorf("read %s: %w", path, err)
	}
	return nil
}
