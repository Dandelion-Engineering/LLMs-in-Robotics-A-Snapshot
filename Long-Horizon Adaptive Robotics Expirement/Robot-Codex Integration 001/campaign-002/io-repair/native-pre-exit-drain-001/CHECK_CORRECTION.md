# Source-binding correction after checks036

The first complete check retained 445 harness tests with five failures, and 556 assessment tests with 18 failures and 16 errors. The new pre-exit sequencing and independent proof tests passed. All five harness failures came from the exact historical runtime parity check seeing the newly declared callback assignment; the assessment failures came from the readonly mirror/canary source allowlists rejecting that same new runtime identity. No empirical launch occurred.

The correction removes exactly the one declared callback-assignment line before the existing historical parity reversal, without changing the old expected hashes. The mirror and canary readers admit only the exact prior runtime identity and the new runtime identity, retain the actual consumed hash, and still reject unknown or ambiguous source archives. A dedicated test verifies complete-byte equality after reversing that one line and tests old/current, missing, changed and duplicate inputs. Raw model output parsing, read grammar, continuity/epoch checks and all original runtime methods remain unchanged.

The original failed checks036 and focused checks001/002 remain retained. A fresh full check is required after the correction and complete prospective source inventory are ready.
