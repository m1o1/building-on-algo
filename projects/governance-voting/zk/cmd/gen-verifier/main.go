// Command gen-verifier compiles the vote circuit, runs the PLONK setup against
// the Perpetual Powers of Tau BN254 structured reference string that AlgoPlonk
// embeds, and writes four artifacts into ./generated:
//
//	vote_circuit.ccs   the compiled constraint system
//	vote_circuit.pk    the proving key
//	vote_circuit.vk    the verifying key
//	VoteVerifier.py    the PuyaPy LogicSig verifier for this verifying key
//
// Everything it writes is reproducible: the SRS is fixed, the circuit is fixed,
// and gnark's setup is deterministic, so re-running this command against the
// same module versions produces byte-identical files.
//
// Usage, from the zk/ directory:
//
//	go run ./cmd/gen-verifier
package main

import (
	"bufio"
	"fmt"
	"io"
	"os"
	"path/filepath"

	"github.com/consensys/gnark-crypto/ecc"
	ap "github.com/giuliop/algoplonk"
	"github.com/giuliop/algoplonk/setup"
	"github.com/giuliop/algoplonk/verifier"

	"zk-voting/circuit"
)

const generatedDir = "generated"

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "gen-verifier:", err)
		os.Exit(1)
	}
}

func run() error {
	if err := os.MkdirAll(generatedDir, 0o755); err != nil {
		return err
	}

	// 1. Compile the circuit and run the PLONK setup.
	//
	// setup.PerpetualPowersOfTauBN254 is a real ceremony SRS, embedded in the
	// AlgoPlonk module as setup/PerpetualPowersOfTauBN254/{pk,vk}.bin and
	// derived from powersOfTau28_hez_final_18.ptau. setup.TestOnlyBN254 would
	// also compile and prove, but its toxic waste is generated locally and is
	// therefore known, so proofs under it are unsound against anyone who runs
	// the same code.
	var c circuit.VoteCircuit
	compiled, err := ap.Compile(&c, ecc.BN254, setup.PerpetualPowersOfTauBN254)
	if err != nil {
		return fmt.Errorf("compile: %w", err)
	}
	fmt.Printf("constraints:    %d\n", compiled.Ccs.GetNbConstraints())
	fmt.Printf("public inputs:  %d\n", compiled.Ccs.GetNbPublicVariables())
	fmt.Printf("secret inputs:  %d\n", compiled.Ccs.GetNbSecretVariables())

	// 2. Write the compiled circuit and both keys, so `prove` does not re-run
	//    the setup and so a reader can inspect exactly what was committed.
	for _, a := range []struct {
		name string
		w    io.WriterTo
	}{
		{"vote_circuit.ccs", compiled.Ccs},
		{"vote_circuit.pk", compiled.Pk},
		{"vote_circuit.vk", compiled.Vk},
	} {
		path := filepath.Join(generatedDir, a.name)
		n, err := writeArtifact(path, a.w)
		if err != nil {
			return err
		}
		fmt.Printf("wrote %-24s %9d bytes\n", path, n)
	}

	// 3. Write the PuyaPy LogicSig verifier for this verifying key. The
	//    verifying key is baked into the program, so the LogicSig's address is
	//    a commitment to this circuit and no other.
	//
	//    AlgoPlonk names the logicsig inside the file after
	//    verifier.DefaultFileName ("Verifier"), which is what puyapy will call
	//    its TEAL output regardless of what this file is called;
	//    scripts/build_verifier.py renames that output to match.
	puyaPath := filepath.Join(generatedDir, "VoteVerifier.py")
	if err := compiled.WritePuyaPyVerifier(puyaPath, verifier.LogicSig); err != nil {
		return fmt.Errorf("write verifier: %w", err)
	}
	info, err := os.Stat(puyaPath)
	if err != nil {
		return err
	}
	fmt.Printf("wrote %-24s %9d bytes\n", puyaPath, info.Size())

	return nil
}

func writeArtifact(path string, w io.WriterTo) (int64, error) {
	f, err := os.Create(path)
	if err != nil {
		return 0, err
	}
	defer f.Close()

	buf := bufio.NewWriter(f)
	n, err := w.WriteTo(buf)
	if err != nil {
		return n, fmt.Errorf("write %s: %w", path, err)
	}
	if err := buf.Flush(); err != nil {
		return n, err
	}
	return n, nil
}
