// Pre-script for the first import of swkotor.exe: turns on the analyzers that make the
// decompiler's output better at the cost of a longer first analysis.
// @category KOTOR

import ghidra.app.script.GhidraScript;

public class SetAnalysisOptions extends GhidraScript {
    @Override
    protected void run() throws Exception {
        // Commits parameter counts and __thiscall to function signatures, so callers decompile
        // with the right arguments instead of in_ECX / extraout guesses.
        setAnalysisOption(currentProgram, "Decompiler Parameter ID", "true");
        println("KOTOR: analysis options set");
    }
}
